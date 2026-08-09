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
    Topic("openai_news", "OpenAI News", "openai_news_pending.txt", "#17725c", 30),
    Topic("langchain_blog", "LangChain Blog", "langchain_blog_pending.txt", "#1d7782", 40),
    Topic("claude_code", "Claude Code", "claude_code_pending.txt", "#64546c", 50),
    Topic("github_copilot_cli", "GitHub Copilot CLI", "copilot_cli_pending.txt", "#3169b0", 60),
    Topic("huggingface_blog", "Hugging Face Blog", "huggingface_blog_pending.txt", "#d97706", 70),
    Topic("google_research", "Google Research", "google_research_pending.txt", "#4285f4", 80),
    Topic("metr", "METR", "metr_pending.txt", "#6d28d9", 90),
    Topic("swe_bench", "SWE-bench", "swe_bench_pending.txt", "#b45309", 100),
    Topic("trail_of_bits", "Trail of Bits", "trail_of_bits_pending.txt", "#b91c1c", 110),
    Topic("owasp_llm_top10", "OWASP LLM Top 10", "owasp_llm_top10_pending.txt", "#991b1b", 120),
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


_GENERIC_LINK_TITLES = {"查看详情", "查看原文", "详情", "原文", "链接"}
_STATUS_PREFIXES = (
    "发现 ",
    "今日 trending",
    "今日无",
    "无更新",
    "首次运行",
    "首次成功",
    "无法获取",
)


def _plain_markdown(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"^\s*[-*]\s+", "", value)
    return value.strip(" \t:-")


def _entry_summary(lines: list[str], *, title: str, url: str) -> str:
    summary: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "---":
            continue
        if url in line or re.fullmatch(r"\*\*.*\*\*", line):
            continue
        plain = _plain_markdown(line)
        if not plain or plain == title or plain.startswith(_STATUS_PREFIXES):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", plain):
            continue
        if plain.startswith(("发布时间:", "📅")):
            continue
        for prefix in ("原文摘要：", "原文摘要:"):
            if plain.startswith(prefix):
                plain = plain[len(prefix) :].strip()
        summary.append(plain)
    return " ".join(summary).strip()


def extract_entries(text: str) -> list[dict[str, str]]:
    """Extract article/project rows from the monitor's Markdown-like sections."""
    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    lines = text.splitlines()

    for index, line in enumerate(lines):
        match = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", line)
        if not match:
            continue
        link_title, url = match.group(1).strip(), match.group(2).strip()
        if url in seen_urls:
            continue
        title = link_title
        if link_title in _GENERIC_LINK_TITLES:
            for previous in reversed(lines[max(0, index - 3) : index]):
                candidate = _plain_markdown(previous)
                if candidate and not candidate.startswith("#"):
                    title = candidate
                    break
        trailing = _plain_markdown(line[match.end() :])
        entry = {"title": title or url, "url": url}
        if trailing:
            entry["meta"] = trailing.strip("() ")
        summary = _entry_summary(lines[index + 1 : index + 8], title=title, url=url)
        if summary:
            entry["summary"] = summary
        entries.append(entry)
        seen_urls.add(url)

    for block in re.split(r"\n\s*---+\s*\n", text):
        url_match = re.search(r"https?://[^\s)>\]]+", block)
        title_match = re.search(r"\*\*([^*\n]+)\*\*", block)
        if not url_match:
            continue
        url = url_match.group(0).rstrip(".,;")
        if url in seen_urls:
            continue
        title = _plain_markdown(title_match.group(1)) if title_match else ""
        if not title:
            before_url = block[: url_match.start()].splitlines()
            for previous in reversed(before_url):
                candidate = _plain_markdown(previous)
                if candidate and not candidate.startswith("#") and not candidate.startswith(_STATUS_PREFIXES):
                    title = candidate.removeprefix("🔗").strip()
                    break
        entry = {"title": title or url, "url": url}
        summary = _entry_summary(block.splitlines(), title=title, url=url)
        if summary:
            entry["summary"] = summary
        entries.append(entry)
        seen_urls.add(url)

    return entries


def section_status(text: str, entries: list[dict[str, str]]) -> str:
    if entries:
        return "content"
    lowered = text.lower()
    if any(
        marker in lowered
        for marker in (
            "今日无新",
            "无更新",
            "首次运行",
            "首次成功抓取",
            "无法获取",
        )
    ):
        return "no_update"
    return "note"


def summarize(text: str, limit: int = 96) -> str:
    compact = " ".join(line.strip(" -*#\t") for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def make_report_id(date: str, full_text: str) -> str:
    digest = hashlib.sha1(full_text.encode("utf-8")).hexdigest()[:10]
    return f"{date}-{digest}"


def project_digest(project: dict[str, Any], limit: int = 420) -> str:
    """Build a compact but decision-useful Chinese summary for chat delivery."""
    intro = project.get("project_intro")
    intro = intro if isinstance(intro, dict) else {}
    candidates = [
        intro.get("tagline"),
        intro.get("problem"),
    ]
    why_choose = intro.get("why_choose")
    if isinstance(why_choose, list) and why_choose:
        candidates.append("适合选择：" + "；".join(str(value) for value in why_choose[:2]))
    if not any(str(value or "").strip() for value in candidates):
        candidates = [project.get("zh_summary"), project.get("description")]

    sentences: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        sentence = " ".join(str(value or "").split()).strip(" 。；")
        identity = sentence.casefold()
        if not sentence or identity in seen:
            continue
        seen.add(identity)
        sentences.append(sentence + ("。" if not sentence.endswith(("。", "！", "？")) else ""))
    digest = "".join(sentences)
    if len(digest) <= limit:
        return digest
    return digest[: limit - 1].rstrip("，；。 ") + "…"


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
        entries = extract_entries(body)
        items.append(
            {
                "topic": topic.key,
                "topic_name": topic.name,
                "title": topic.name,
                "summary": summarize(body),
                "body": body,
                "links": extract_links(body),
                "entries": entries,
                "status": section_status(body, entries),
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
        "delivery_source": "daily_summary",
    }


def attach_trending_projects(
    payload: dict[str, Any],
    projects: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replace parsed Trending text rows with their structured project data."""
    result = dict(payload)
    items = [dict(item) for item in payload.get("items") or []]
    for item in items:
        if item.get("topic") != "github_trending":
            continue
        entries = []
        for project in projects:
            full_name = str(project.get("full_name") or "").strip()
            source_url = str(
                project.get("source_url")
                or project.get("url")
                or (f"https://github.com/{full_name}" if full_name else "")
            )
            intro_url = str(project.get("intro_url") or "")
            if not full_name or not source_url:
                continue
            entry = {
                "full_name": full_name,
                "title": full_name,
                "summary": project_digest(project),
                "url": intro_url or source_url,
                "intro_url": intro_url,
                "source_url": source_url,
                "project_intro": project.get("project_intro") or {},
            }
            entries.append(entry)
        if entries:
            item["entries"] = entries
            item["links"] = [
                {"title": entry["title"], "url": entry["url"]}
                for entry in entries
            ]
            item["status"] = "content"
    result["items"] = items
    return result
