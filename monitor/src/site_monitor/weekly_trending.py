#!/usr/bin/env python3
"""Independent weekly GitHub Trending snapshot and Feishu delivery."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys

from .check_github_trending import (
    fetch_repo_description,
    fetch_trending,
    parse_trending,
    zh,
)
from .delivery import is_enabled, send_report
from .monitor_config import runtime_dir, runtime_path
from .postprocess import apply_postprocessors


STATE_FILE = runtime_path("state", "github_trending_weekly_state.json")
WEEKLY_URL = "https://github.com/trending?since=weekly"
MAX_REPOS = 10


def _log(message: str) -> None:
    print(f"[weekly-trending] {message}", file=sys.stderr)


def _week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _load_state() -> dict:
    try:
        return json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    path = Path(STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_weekly_payload(repos: list[dict], *, now: datetime | None = None) -> dict:
    now = now or datetime.now().astimezone()
    date = now.strftime("%Y-%m-%d")
    week_key = _week_key(now)
    entries = []
    lines = [f"🔥 **本周 GitHub Trending** — {week_key}", ""]
    for index, repo in enumerate(repos, 1):
        full_name = str(repo.get("full_name") or "")
        source_url = str(repo.get("source_url") or repo.get("url") or f"https://github.com/{full_name}")
        intro_url = str(repo.get("intro_url") or "")
        summary = str(repo.get("zh_summary") or (zh(repo.get("description", "")) if repo.get("description") else ""))
        entries.append(
            {
                "full_name": full_name,
                "title": full_name,
                "summary": summary,
                "url": intro_url or source_url,
                "intro_url": intro_url,
                "source_url": source_url,
                "project_intro": repo.get("project_intro") or {},
            }
        )
        lines.extend([f"**{index}. {full_name}**", summary, f"🔗 {intro_url or source_url}", ""])
    return {
        "report_id": f"weekly-{week_key}",
        "date": date,
        "title": f"本周 GitHub Trending — {week_key}",
        "full_text": "\n".join(line for line in lines if line is not None).strip(),
        "generated_at": now.isoformat(timespec="seconds"),
        "items": [
            {
                "topic": "github_trending_weekly",
                "topic_name": "本周 GitHub Trending",
                "title": "本周 GitHub Trending",
                "status": "content",
                "color": "#24292f",
                "order": 10,
                "entries": entries,
            }
        ],
        "item_count": 1,
    }


def main() -> int:
    now = datetime.now().astimezone()
    week_key = _week_key(now)
    force = os.environ.get("SITE_MONITOR_FORCE_WEEKLY", "").lower() in {"1", "true", "yes"}
    state = _load_state()
    if state.get("last_report_week") == week_key and not force:
        _log(f"{week_key} 已推送，跳过")
        return 0

    store = None
    mongo_uri = os.environ.get("SITE_MONITOR_MONGO_URI")
    if mongo_uri:
        from .mongo_store import create_store

        store = create_store(mongo_uri, os.environ.get("SITE_MONITOR_DB_NAME", "site_monitor"))
        restored = store.restore_monitor_state(runtime_dir("state"))
        _log(f"MongoDB 状态恢复完成: files={restored}")
        state = _load_state()
        if state.get("last_report_week") == week_key and not force:
            _log(f"{week_key} 已推送，跳过")
            return 0

    html = fetch_trending(WEEKLY_URL)
    if not html:
        raise RuntimeError("无法获取 GitHub weekly trending")
    repos = parse_trending(html)[:MAX_REPOS]
    if not repos:
        raise RuntimeError("GitHub weekly trending 未解析到项目")
    for repo in repos:
        if not repo.get("description") and "/" in repo.get("full_name", ""):
            owner, name = repo["full_name"].split("/", 1)
            repo["description"] = fetch_repo_description(owner, name)
    repos = apply_postprocessors("github_trending", {"repos": repos}).get("repos", repos)
    payload = build_weekly_payload(repos, now=now)

    if not is_enabled():
        _log("delivery 未启用")
        print(payload["full_text"])
        return 0
    result = send_report(payload["full_text"], payload=payload)
    if not result.get("success"):
        raise RuntimeError(f"周榜发送失败: {result}")
    _log(f"发送成功 ({result.get('provider', '未知')}): {len(repos)} 个项目")

    state.update(
        {
            "last_report_week": week_key,
            "last_check": now.isoformat(timespec="seconds"),
            "last_repos": [repo.get("full_name") for repo in repos],
        }
    )
    _save_state(state)
    if store is not None:
        entries = payload["items"][0]["entries"]
        intros = store.upsert_project_intros(entries)
        saved = store.save_monitor_state(runtime_dir("state"))
        _log(f"MongoDB 写入成功: project_intros={intros} state_files={saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
