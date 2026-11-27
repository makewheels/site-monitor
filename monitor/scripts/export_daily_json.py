#!/usr/bin/env python3
"""把每天推送的内容导出成按年/月分目录的 JSON 存档。

输出：monitor/data/archive/<YYYY>/<MM>/<YYYY-MM-DD>.json

每天 GitHub Actions 跑完日报后会调用一次，把当天的报告、条目和投递结果落到存档，
随同 monitor/data 一起提交，这样：
  1. 以后可以直接读 git 历史里的存档，不依赖数据库；
  2. 仓库每天有提交，避免 GitHub 因长期无活动自动停用定时工作流。

用法：
  uv run python scripts/export_daily_json.py            # 补齐所有历史报告
  uv run python scripts/export_daily_json.py --date 2026-11-28
  uv run python scripts/export_daily_json.py --force    # 覆盖已存在的文件
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"


def load(name: str):
    path = DATA / name
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def write_report(report: dict, items: list[dict], events: list[dict], force: bool) -> Path:
    date = (report.get("date") or report.get("created_at") or "")[:10]
    if not date or len(date) < 10:
        raise ValueError(f"报告缺少日期：{report.get('report_id')}")
    year, month = date[:4], date[5:7]
    folder = ARCHIVE / year / month
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date}.json"

    report_id = report.get("report_id", "")
    previous_ids: list[str] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
        if existing.get("report_id") == report_id and not force:
            return path
        previous_ids = list(existing.get("same_day_reports") or [])
        if existing.get("report_id") and existing["report_id"] != report_id:
            previous_ids.append(existing["report_id"])

    payload = {
        "date": date,
        "report_id": report_id,
        "created_at": report.get("created_at", ""),
        "exported_at": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "full_text": report.get("full_text", ""),
        "item_count": len(items),
        "same_day_reports": previous_ids,
        "items": [
            {
                "topic": item.get("topic", ""),
                "topic_name": item.get("topic_name", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "summary": item.get("summary", ""),
                "body": item.get("body", ""),
                "links": item.get("links", []),
            }
            for item in items
        ],
        "deliveries": [
            {
                "delivered_at": event.get("delivered_at", ""),
                "provider": event.get("provider", ""),
                "status": event.get("status", ""),
                "message_count": event.get("message_count"),
            }
            for event in events
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="只导出某一天（YYYY-MM-DD）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在且 report_id 相同 的文件")
    args = parser.parse_args()

    reports = load("reports.json")
    items_all = load("report_items.json")
    events_all = load("delivery_events.json")

    if args.date:
        reports = [r for r in reports if (r.get("date") or "")[:10] == args.date]

    written, skipped = 0, 0
    for report in reports:
        report_id = report.get("report_id", "")
        items = [i for i in items_all if i.get("report_id") == report_id]
        events = [e for e in events_all if e.get("report_id") == report_id]
        path = write_report(report, items, events, args.force)
        if path.exists():
            written += 1
    print(f"导出 {written} 个存档文件（跳过重复 {skipped}），目录 {ARCHIVE}")


if __name__ == "__main__":
    main()