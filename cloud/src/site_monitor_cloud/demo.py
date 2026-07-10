"""Local demo API for trying the Android app without MongoDB."""
from __future__ import annotations

import os
from typing import Any

from .api import create_app


TOPICS = [
    {"key": "github_trending", "name": "GitHub Trending", "color": "#24292f", "order": 10},
    {"key": "anthropic_engineering", "name": "Anthropic Engineering", "color": "#a35e24", "order": 20},
    {"key": "openai_news", "name": "OpenAI News", "color": "#17725c", "order": 30},
    {"key": "langchain_blog", "name": "LangChain Blog", "color": "#1d7782", "order": 40},
    {"key": "claude_code", "name": "Claude Code", "color": "#64546c", "order": 50},
]


class DemoStore:
    def __init__(self):
        payload = {
            "report_id": "2026-07-10-demo",
            "date": "2026-07-10",
            "title": "每日 AI 监控汇总 — 2026-07-10",
            "generated_at": "2026-07-10T07:00:00",
            "topics": TOPICS,
            "items": [
                {
                    "report_id": "2026-07-10-demo",
                    "item_id": "2026-07-10-demo:github_trending",
                    "date": "2026-07-10",
                    "topic": "github_trending",
                    "topic_name": "GitHub Trending",
                    "title": "GitHub Trending",
                    "status": "content",
                    "color": "#24292f",
                    "order": 10,
                    "entries": [
                        {
                            "title": "example/agent-runtime",
                            "summary": "多代理运行时与工具编排示例",
                            "url": "https://github.com/example/agent-runtime",
                        }
                    ],
                    "links": [
                        {
                            "title": "example/agent-runtime",
                            "url": "https://github.com/example/agent-runtime",
                        }
                    ],
                },
                {
                    "report_id": "2026-07-10-demo",
                    "item_id": "2026-07-10-demo:openai_news",
                    "date": "2026-07-10",
                    "topic": "openai_news",
                    "topic_name": "OpenAI News",
                    "title": "OpenAI News",
                    "status": "content",
                    "color": "#17725c",
                    "order": 30,
                    "entries": [
                        {
                            "title": "OpenAI 官方更新示例",
                            "url": "https://openai.com/news/",
                        }
                    ],
                    "links": [
                        {"title": "OpenAI News", "url": "https://openai.com/news/"}
                    ],
                },
            ],
        }
        payload["item_count"] = len(payload["items"])
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
        return TOPICS


def main() -> None:
    os.environ.setdefault("SITE_MONITOR_APP_TOKEN", "dev-token")
    os.environ.setdefault("SITE_MONITOR_UPLOAD_TOKEN", "dev-upload-token")
    host = os.environ.get("SITE_MONITOR_DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("SITE_MONITOR_DEMO_PORT", "5001"))
    app = create_app(DemoStore())
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
