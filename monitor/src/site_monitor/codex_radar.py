#!/usr/bin/env python3
"""Codex 雷达即时推送。

监控 https://codexradar.com/feed.xml(Codex 速蹬窗口/额度硬重置事件流)。
发现新的「窗口开启」条目时,立即用 delivery.send_report 发飞书。

与每日日报(daily_summary)解耦:本模块独立运行,只推 Codex 雷达的新开启事件。
去重 state 走 runtime/state/codex_radar_state.json,有 Mongo 时自动随
mongo_store 的 save/restore 机制持久化,跨 CI 运行保持去重。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from .delivery import is_enabled, send_report
from .monitor_config import PROJECT_ROOT, runtime_dir, runtime_path

FEED_URL = "https://codexradar.com/feed.xml"
STATE_FILE = runtime_path("state", "codex_radar_state.json")
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}
# 只推标题含这些关键词的条目(「开启」类)
OPEN_KEYWORDS = ("开启", "open", "重置")
MAX_KNOWN = 200  # known_guids 保留上限,防无限增长


def _log(msg):
    print(f"[codex-radar] {msg}", file=sys.stderr)


def fetch_feed(url=FEED_URL):
    """抓取并解析 feed,返回条目列表(每项 title/link/guid/published/summary)。"""
    try:
        import feedparser
    except ImportError:
        _log("RSS 解析失败: 缺少 feedparser")
        return []

    try:
        req = urllib.request.Request(url, headers=FEED_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        feed = feedparser.parse(content)
    except Exception as exc:
        _log(f"抓取失败: {exc}")
        return []

    entries = []
    for e in feed.entries:
        link = e.get("link", "")
        guid = e.get("id") or e.get("guid") or link
        title = e.get("title", "").strip() or link
        if not guid:
            continue
        summary = (e.get("summary") or e.get("description") or "").strip()
        entries.append({
            "title": title,
            "link": link,
            "guid": guid,
            "published": e.get("published", e.get("updated", "")),
            "summary": summary,
        })
    return entries


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"known_guids": [], "last_check": None}


def save_state(state):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_open_event(title):
    t = title.lower()
    return any(k.lower() in t for k in OPEN_KEYWORDS) and "关闭" not in title


def build_message(items):
    """拼成飞书 markdown 消息。"""
    lines = ["🚨 **Codex 雷达:速蹬窗口开启提醒**", ""]
    for it in items:
        lines.append(f"**{it['title']}**")
        if it.get("published"):
            lines.append(f"🕐 {it['published']}")
        if it.get("summary"):
            s = it["summary"].replace("\n", " ").strip()
            if len(s) > 600:
                s = s[:600] + "…"
            lines.append(f"📝 {s}")
        if it.get("link"):
            lines.append(f"🔗 {it['link']}")
        lines.append("")
    lines.append(f"_{datetime.now().strftime('%Y-%m-%d %H:%M')} codexradar.com_")
    return "\n".join(lines)


def main():
    mongo_uri = os.environ.get("SITE_MONITOR_MONGO_URI")
    store = None
    if mongo_uri:
        try:
            from .mongo_store import create_store
            db_name = os.environ.get("SITE_MONITOR_DB_NAME", "site_monitor")
            store = create_store(mongo_uri, db_name)
            restored = store.restore_monitor_state(runtime_dir("state"))
            _log(f"MongoDB 状态恢复完成: files={restored}")
        except Exception as exc:
            _log(f"⚠️ MongoDB 连接失败,改用本地 state: {exc}")
            store = None

    entries = fetch_feed()
    if not entries:
        _log("feed 无条目或抓取失败,退出")
        return 0

    state = load_state()
    known = set(state.get("known_guids", []))
    first_run = not os.path.exists(STATE_FILE) and not known

    new_entries = [e for e in entries if e["guid"] not in known]
    new_open = [e for e in new_entries if is_open_event(e["title"])]

    if first_run:
        # 首跑:推当前最新一条「开启」事件确认链路通,其余记为已知不发
        to_send = [e for e in entries if is_open_event(e["title"])][:1]
        _log(f"首次运行,feed {len(entries)} 条,推最新 1 条开启事件确认链路")
    else:
        to_send = new_open
        _log(f"feed {len(entries)} 条,新 {len(new_entries)} 条,新开启 {len(new_open)} 条")

    if to_send:
        if is_enabled():
            message = build_message(to_send)
            try:
                result = send_report(message, payload={"full_text": message})
                if result.get("skipped"):
                    _log(f"发送跳过: {result.get('reason')}")
                elif not result.get("success", False):
                    _log(f"⚠️ 发送失败: {result}")
                    return 1
                else:
                    _log(f"发送成功 ({result.get('provider', '未知')}): {len(to_send)} 条")
            except Exception as exc:
                _log(f"⚠️ 发送异常: {exc}")
                return 1
        else:
            _log("delivery 未启用,跳过发送")
            print(build_message(to_send))

    all_guids = [e["guid"] for e in entries]
    state["known_guids"] = all_guids[-MAX_KNOWN:]
    state["last_check"] = datetime.now().isoformat()
    save_state(state)

    if store:
        try:
            saved = store.save_monitor_state(runtime_dir("state"))
            _log(f"MongoDB 状态存回: files={saved}")
        except Exception as exc:
            _log(f"⚠️ MongoDB 状态存回失败: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
