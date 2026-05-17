"""Postprocessors for changelog-style monitor entries."""
import re
from typing import Any

FEATURE_KEYWORDS = (
    "add", "added", "adds", "new", "introduce", "introduced", "support",
    "supports", "enable", "enabled", "allow", "allows", "breaking",
    "deprecat", "remove", "removed", "security", "permission", "plugin",
    "mcp", "agent", "agents", "command", "commands", "flag", "flags",
    "setting", "settings", "config", "model", "models", "hook", "hooks",
    "skill", "skills", "workflow", "install", "auth", "login", "sdk",
    "api", "tool", "tools", "memory", "performance",
)

FIX_PREFIX_RE = re.compile(
    r"^(fix|fixed|fixes|bugfix|resolve|resolved|crash|docs?|documentation|"
    r"dependency|dependencies|deps|ci|tests?|chore|internal|refactor|lint|format)\b",
    re.IGNORECASE,
)

CRITICAL_FIX_KEYWORDS = ("security", "permission", "data loss", "breaking")


def _clean_lines(body: str) -> list[str]:
    lines = []
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("**full changelog**", "full changelog")):
            continue
        line = re.sub(r"^[*\-]\s+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def _is_feature_line(line: str) -> bool:
    lowered = line.lower()
    if FIX_PREFIX_RE.search(line) and not any(keyword in lowered for keyword in CRITICAL_FIX_KEYWORDS):
        return False
    return any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in FEATURE_KEYWORDS)


def _format_section(heading: str, lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {heading}\n{body}"


def split_changelog_sections(payload: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Split changelog body into feature and fix/other sections."""
    options = options or {}
    lines = payload.get("lines") or _clean_lines(payload.get("body", ""))
    feature_lines = [line for line in lines if _is_feature_line(line)]
    fix_lines = [line for line in lines if line not in feature_lines]

    feature_heading = options.get("feature_heading", "功能更新")
    fix_heading = options.get("fix_heading", "修复/其他")
    include_fixes = bool(options.get("include_fixes", True))
    notify_only_feature_updates = bool(options.get("notify_only_feature_updates", False))

    sections = []
    if feature_lines:
        sections.append(_format_section(feature_heading, feature_lines[:8]))
    elif fix_lines and include_fixes:
        sections.append(f"### {feature_heading}\n- 暂无明显功能更新")

    if include_fixes and fix_lines:
        fix_section = _format_section(fix_heading, fix_lines[:8])
        sections.append(f"---\n{fix_section}" if sections else fix_section)

    payload["summary"] = "\n\n".join(sections)
    payload["feature_count"] = len(feature_lines)
    payload["fix_count"] = len(fix_lines)
    payload["should_notify"] = bool(feature_lines) or (include_fixes and not notify_only_feature_updates)
    return payload
