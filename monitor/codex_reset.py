#!/usr/bin/env python3
"""Codex 用量额度重置提醒。

数据源是公开的 Codex 重置追踪站 RSS（不需要登录），只认 Codex 条目，
按发布时间窗口判断"新公告"，避免引入额外状态存储：每小时跑一次，
只推送最近 WINDOW_HOURS 小时内的条目。

环境变量：
  CODEX_RESET_FEED        覆盖默认 RSS 地址
  CODEX_RESET_CHAT_ID     推送的飞书群（默认读 FEISHU_CHAT_ID）
  FEISHU_APP_ID / FEISHU_APP_SECRET  飞书自建应用凭据
  CODEX_RESET_WINDOW_HOURS  时间窗口，默认 3
  CODEX_RESET_DRY_RUN=1   只打印不发送
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

DEFAULT_FEED = "https://aiidelist.com/codex-reset.xml"
FEISHU_BASE = os.getenv("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/")


def window_hours() -> float:
    try:
        return float(os.getenv("CODEX_RESET_WINDOW_HOURS", "3"))
    except ValueError:
        return 3.0


def fetch_items(feed_url: str) -> list[dict]:
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"RSS 解析失败：{feed_url}")

    items = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        if "codex" not in title.lower():
            continue
        raw_date = entry.get("published") or entry.get("updated") or ""
        try:
            published = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            published = None
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        items.append({
            "title": title,
            "link": entry.get("link") or "",
            "summary": (entry.get("summary") or "").strip(),
            "published": published,
        })
    return items


def feishu_token(app_id: str, app_secret: str) -> str:
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    request = urllib.request.Request(
        f"{FEISHU_BASE}/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"获取 tenant_access_token 失败：{data.get('msg')}")
    return token


def build_card(item: dict) -> dict:
    kind = "banked reset" if "banked" in item["title"].lower() else "重置公告"
    when = item["published"].astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    summary = item["summary"][:600] or "（无摘要）"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": f"Codex 额度重置 · {kind}"},
        },
        "elements": [
            {"tag": "markdown", "content": f"**{item['title']}**"},
            {"tag": "markdown", "content": summary},
            {"tag": "hr"},
            {"tag": "markdown", "content": f"公告时间 {when}（北京时间）"},
            {"tag": "markdown", "content": f"[查看原文]({item['link']})"},
        ],
    }


def send_card(token: str, chat_id: str, card: dict) -> dict:
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }).encode()
    request = urllib.request.Request(
        f"{FEISHU_BASE}/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    feed_url = os.getenv("CODEX_RESET_FEED", DEFAULT_FEED)
    hours = window_hours()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    fresh = [item for item in fetch_items(feed_url) if item["published"] >= cutoff]
    print(f"窗口 {hours}h 内的 Codex 条目：{len(fresh)} 条")
    if not fresh:
        return 0

    chat_id = os.getenv("CODEX_RESET_CHAT_ID") or os.getenv("FEISHU_CHAT_ID", "")
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not (chat_id and app_id and app_secret):
        print("缺少飞书配置，跳过推送")
        return 0

    if os.getenv("CODEX_RESET_DRY_RUN") == "1":
        for item in fresh:
            print(json.dumps(build_card(item), ensure_ascii=False)[:300])
        return 0

    token = feishu_token(app_id, app_secret)
    for item in sorted(fresh, key=lambda x: x["published"]):
        result = send_card(token, chat_id, build_card(item))
        print(f"推送 {item['title'][:40]} → code={result.get('code')} msg={result.get('msg')}")
        if result.get("code") != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())