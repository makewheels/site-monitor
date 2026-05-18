"""Structured report payloads for the mobile app and cloud sync."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Any


@dataclass(frozen=True)
class Topic:
    key: str
    name: str
    pending_file: str
    color: str
    order: int


TOPICS: tuple[Topic, ...] = (
    Topic("github_trending", "GitHub Trending", "github_trending_pending.txt", "#24292f", 10),
    Topic("anthropic_engineering", "Anthropic Engineering", "anthropic_pending.txt", "#a35e24", 20),
    Topic("openai_engineering", "OpenAI Engineering", "openai_engineering_pending.txt", "#17725c", 30),
    Topic("langchain_blog", "LangChain Blog", "langchain_blog_pending.txt", "#1d7782", 40),
    Topic("claude_code", "Claude Code", "claude_code_pending.txt", "#64546c", 50),
    Topic("github_copilot_cli", "GitHub Copilot CLI", "copilot_cli_pending.txt", "#3169b0", 60),
)


def topics_payload() -> list[dict[str, Any]]:
    return [
        {
            "key": topic.key,
            "name": topic.name,
            "color": topic.color,
            "order": topic.order,
        }
        for topic in TOPICS
    ]


def extract_links(text: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        title, url = match.group(1).strip(), match.group(2).strip()
        if url not in seen:
            links.append({"title": title or url, "url": url})
            seen.add(url)

    for match in re.finditer(r"(?<!\()https?://[^\s)>\]]+", text):
        url = match.group(0).rstrip(".,;")
        if url not in seen:
            links.append({"title": url, "url": url})
            seen.add(url)

    return links


def summarize(text: str, limit: int = 96) -> str:
    compact = " ".join(line.strip(" -*#\t") for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def make_report_id(date: str, full_text: str) -> str:
    digest = hashlib.sha1(full_text.encode("utf-8")).hexdigest()[:10]
    return f"{date}-{digest}"


def build_payload(
    sections: dict[str, str],
    *,
    date: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    date = date or datetime.now().strftime("%Y-%m-%d")
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")

    items: list[dict[str, Any]] = []
    for topic in TOPICS:
        body = sections.get(topic.key, "").strip()
        if not body:
            continue
        items.append(
            {
                "topic": topic.key,
                "topic_name": topic.name,
                "title": topic.name,
                "summary": summarize(body),
                "body": body,
                "links": extract_links(body),
                "color": topic.color,
                "order": topic.order,
            }
        )

    full_text_sections = [f"📊 **每日 AI 监控汇总** — {date}"]
    full_text_sections.extend(item["body"] for item in items)
    full_text = "\n\n".join(full_text_sections).strip()
    report_id = make_report_id(date, full_text)

    for item in items:
        item["report_id"] = report_id
        item["item_id"] = f"{report_id}:{item['topic']}"
        item["date"] = date
        item["created_at"] = generated_at

    return {
        "report_id": report_id,
        "date": date,
        "title": f"每日 AI 监控汇总 — {date}",
        "full_text": full_text,
        "generated_at": generated_at,
        "topics": topics_payload(),
        "items": items,
        "item_count": len(items),
    }
