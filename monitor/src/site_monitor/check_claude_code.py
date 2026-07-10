#!/usr/bin/env python3
"""检查 Claude Code changelog 更新。"""
import json
import os
import re
import html
from datetime import datetime
from .monitor_config import get_monitor_source, runtime_path
from .postprocess import apply_postprocessors

try:
    import feedparser
except ImportError:
    feedparser = None

STATE_FILE = runtime_path("state", "claude_code_state.json")
PENDING_FILE = runtime_path("pending", "claude_code_pending.txt")
SOURCE_CONFIG = get_monitor_source("claude_code_changelog")
RSSHUB_CHANGELOG_URLS = SOURCE_CONFIG.get("rsshub_urls") or [
    "https://rsshub.app/claude/code/changelog",
    "https://rsshub.ktachibana.party/claude/code/changelog",
]

IMPORTANT_KEYWORDS = (
    "add", "added", "adds", "new", "introduce", "introduced", "support",
    "supports", "enable", "enabled", "allow", "allows", "breaking",
    "deprecat", "remove", "removed", "security", "permission", "plugin",
    "mcp", "agent", "agents", "command", "commands", "flag", "flags",
    "setting", "settings", "config", "model", "models", "hook", "hooks",
    "skill", "skills", "workflow", "install", "auth", "login", "sdk",
    "api", "tool", "tools", "memory", "performance",
)

BUGFIX_ONLY_KEYWORDS = (
    "fix", "fixed", "bug", "bugfix", "crash", "typo", "docs",
    "documentation", "dependency", "dependencies", "deps", "ci", "test",
    "tests", "chore", "internal", "refactor", "lint", "format",
)

BUGFIX_PREFIX_RE = re.compile(
    r"^(fix|fixed|fixes|bugfix|resolve|resolved|crash|docs?|documentation|"
    r"dependency|dependencies|deps|ci|tests?|chore|internal|refactor|lint|format)\b",
    re.IGNORECASE,
)

CRITICAL_FIX_KEYWORDS = ("security", "permission", "data loss", "breaking")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"github_tag": None, "last_check": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def check_rsshub_changelog():
    """通过 RSSHub 检查 Claude Code 官方 changelog。"""
    if not feedparser:
        print("  RSSHub changelog 检查失败: 缺少 feedparser")
        return None

    import urllib.request
    for url in RSSHUB_CHANGELOG_URLS:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            if not feed.entries:
                print(f"  RSSHub changelog 未返回条目: {url}")
                continue

            entry = feed.entries[0]
            version = (entry.get("title") or "").strip()
            if version and not version.startswith("v"):
                tag = f"v{version}"
            else:
                tag = version
            print(f"RSSHub changelog 获取成功: {url}")
            return {
                "tag": tag,
                "version": version,
                "name": version,
                "body": html_to_text(entry.get("description", "")),
                "url": entry.get("link", url),
                "published": entry.get("published", ""),
                "source": url,
            }
        except Exception as e:
            print(f"  RSSHub changelog 检查失败: {url}: {e}")
    return None

def html_to_text(value):
    text = html.unescape(value or "")
    text = re.sub(r"</li>\s*<li>", "\n", text)
    text = re.sub(r"<li>", "", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

def semver_tuple(version):
    """提取 v2.1.143 / 2.1.143 这类版本号，无法解析返回 None。"""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())

def major_or_minor_changed(old_version, new_version):
    old_semver = semver_tuple(old_version)
    new_semver = semver_tuple(new_version)
    if not old_semver or not new_semver:
        return False
    return old_semver[:2] != new_semver[:2]

def meaningful_release_lines(body):
    """保留 release notes 里真正描述变更的行，过滤空行和模板噪音。"""
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

def is_important_release(release, old_tag=None):
    """判断 changelog 是否包含重要功能更新或重要风险项。"""
    tag = release.get("tag", "")
    if old_tag and major_or_minor_changed(old_tag, tag):
        return True

    lines = meaningful_release_lines(release.get("body", ""))
    if not lines:
        return False

    important_hits = []
    for line in lines:
        lowered = line.lower()
        if BUGFIX_PREFIX_RE.search(line) and not any(
            keyword in lowered for keyword in CRITICAL_FIX_KEYWORDS
        ):
            continue
        if any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in IMPORTANT_KEYWORDS):
            important_hits.append(line)

    if important_hits:
        return True

    all_text = " ".join(lines).lower()
    if any(keyword in all_text for keyword in BUGFIX_ONLY_KEYWORDS):
        return False
    return False

def release_summary(body, max_chars=500):
    lines = meaningful_release_lines(body)
    if not lines:
        return ""
    summary = "\n".join(f"- {line}" for line in lines[:6])
    if len(summary) > max_chars:
        return summary[:max_chars].rstrip() + "..."
    return summary

def processed_release_summary(release):
    processed = apply_postprocessors(
        "claude_code_changelog",
        {
            "title": release.get("name") or release.get("tag", ""),
            "body": release.get("body", ""),
            "url": release.get("url", ""),
            "published": release.get("published", ""),
        },
    )
    summary = processed.get("summary") or release_summary(release.get("body", ""))
    return summary, processed

def main():
    state = load_state()
    old_tag = state.get("github_tag")

    release = check_rsshub_changelog()

    has_update = False

    with open(PENDING_FILE, 'w') as f:
        if release and old_tag and release["tag"] != old_tag:
            summary, processed = processed_release_summary(release)
            if not processed.get("should_notify", True):
                print(f"忽略 Claude Code changelog 更新: {release['tag']}")
            else:
                important_release = is_important_release(release, old_tag)
                label = "功能更新" if important_release else "changelog 更新"
                tag = release["tag"]
                f.write(f"## {datetime.now().strftime('%Y-%m-%d')} Claude Code\n\n")
                f.write(f"🆕 **Claude Code {label}**: `{tag}`\n")
                f.write(f"🔗 {release['url']}\n")
                if release["published"]:
                    f.write(f"发布时间: {release['published'][:10]}\n")
                if summary:
                    f.write(f"\n{summary}\n")
                has_update = True
                print(f"Claude Code changelog 更新: {tag}")
        if release:
            tag = release["tag"]
            if not old_tag or tag == old_tag:
                print(f"Claude Code 最新版本: {tag}")
            state["github_tag"] = tag
            state["changelog_source"] = release["source"]

        if not has_update:
            f.truncate(0)
            print("无 Claude Code changelog 更新，不写入晨报")

    state["last_check"] = datetime.now().isoformat()
    save_state(state)

if __name__ == "__main__":
    main()
