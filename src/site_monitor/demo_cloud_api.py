"""Local demo API for trying the Android app without MongoDB."""
from __future__ import annotations

import os
from typing import Any

from .cloud_api import create_app
from .report_payload import build_payload, topics_payload


class DemoStore:
    def __init__(self):
        payload = build_payload(
            {
                "claude_code": (
                    "## 功能更新\n"
                    "- 新增终端集成与权限提示优化 [查看原文](https://code.claude.com/docs/en/changelog)\n\n"
                    "## 修复/其他\n"
                    "- 修复部分命令输出格式问题"
                ),
                "github_trending": (
                    "🔥 GitHub Trending Top 5\n"
                    "1. example/agent-runtime\n"
                    "   多代理运行时样例 https://github.com/example/agent-runtime"
                ),
                "openai_news": (
                    "OpenAI News 新文章\n"
                    "[官方 RSS](https://openai.com/news/rss.xml)"
                ),
            },
            date="2026-05-18",
            generated_at="2026-05-18T07:15:00",
        )
        self.payloads = {payload["report_id"]: payload}

    def upsert_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads[payload["report_id"]] = payload
        return {"report_id": payload["report_id"], "item_count": len(payload.get("items", []))}

    def latest(self) -> dict[str, Any] | None:
        return list(self.payloads.values())[-1]

    def list_reports(self, *, limit: int = 30, topic: str | None = None) -> list[dict[str, Any]]:
        reports = list(self.payloads.values())[:limit]
        if not topic:
            return [
                {
                    "report_id": report["report_id"],
                    "date": report["date"],
                    "title": report["title"],
                    "item_count": report["item_count"],
                    "topics": report["topics"],
                }
                for report in reports
            ]
        return [
            item
            for report in reports
            for item in report.get("items", [])
            if item.get("topic") == topic
        ]

    def detail(self, report_id: str) -> dict[str, Any] | None:
        return self.payloads.get(report_id)

    def topics(self) -> list[dict[str, Any]]:
        return topics_payload()


def main() -> None:
    os.environ.setdefault("SITE_MONITOR_APP_TOKEN", "dev-token")
    os.environ.setdefault("SITE_MONITOR_UPLOAD_TOKEN", "dev-upload-token")
    host = os.environ.get("SITE_MONITOR_DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("SITE_MONITOR_DEMO_PORT", "5001"))
    app = create_app(DemoStore())
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
