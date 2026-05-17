#!/usr/bin/env python3
"""检查 Claude Code (Anthropic) 重要版本更新 - 通过 RSSHub、npm 和 GitHub Releases"""
import json
import subprocess
import os
import re
import html
from datetime import datetime
from monitor_config import get_monitor_source

try:
    import feedparser
except ImportError:
    feedparser = None

STATE_FILE = os.path.expanduser("~/PythonProjects/site_monitor/claude_code_state.json")
PENDING_FILE = os.path.expanduser("~/PythonProjects/site_monitor/claude_code_pending.txt")
SOURCE_CONFIG = get_monitor_source("claude_code_changelog")
RELEASES_URL = SOURCE_CONFIG.get("github_releases_url", "https://github.com/anthropics/claude-code/releases")
GITHUB_RELEASES_API = SOURCE_CONFIG.get(
    "github_releases_api",
    "https://api.github.com/repos/anthropics/claude-code/releases?per_page=5",
)
NPM_PACKAGE = SOURCE_CONFIG.get("npm_package", "@anthropic-ai/claude-code")
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
    return {"npm_version": None, "github_tag": None, "last_check": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def check_npm():
    """通过 npm 检查最新版本"""
    try:
        result = subprocess.run(
            ["npm", "view", NPM_PACKAGE, "version", "--json"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            versions = json.loads(result.stdout)
            if isinstance(versions, list):
                return versions[-1]
            return versions
    except Exception as e:
        print(f"  npm 检查失败: {e}")
    return None

def check_github():
    """通过 GitHub API 检查最新 release"""
    import urllib.request
    try:
        req = urllib.request.Request(GITHUB_RELEASES_API, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/vnd.github.v3+json'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            releases = json.loads(resp.read().decode('utf-8'))
        if releases:
            latest = releases[0]
            return {
                "tag": latest.get("tag_name", ""),
                "name": latest.get("name", ""),
                "body": latest.get("body", ""),
                "url": latest.get("html_url", ""),
                "published": latest.get("published_at", ""),
            }
    except Exception as e:
        print(f"  GitHub 检查失败: {e}")
    return None

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
    """只汇报重要功能更新；纯 bugfix/docs/deps/chore 版本不进晨报。"""
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

def main():
    state = load_state()
    old_npm = state.get("npm_version")
    old_tag = state.get("github_tag")

    # 检查 npm 版本
    npm_ver = check_npm()
    # 优先检查 Claude Code 官方 changelog 的 RSSHub route
    changelog_release = check_rsshub_changelog()
    # 检查 GitHub release
    gh_release = check_github()
    release = changelog_release or gh_release

    has_update = False
    important_release = bool(
        release and old_tag and release["tag"] != old_tag
        and is_important_release(release, old_tag)
    )

    with open(PENDING_FILE, 'w') as f:
        if important_release:
            f.write(f"## {datetime.now().strftime('%Y-%m-%d')} Claude Code\n\n")

        if npm_ver:
            if important_release and old_npm and npm_ver != old_npm:
                f.write(f"🆕 **npm 新版本**: `{npm_ver}` (之前: `{old_npm}`)\n")
                f.write(f"安装: `npm i -g @anthropic-ai/claude-code@{npm_ver}`\n\n")
                has_update = True
                print(f"npm 新版本: {npm_ver}")
            else:
                print(f"npm 版本: {npm_ver}")
            state["npm_version"] = npm_ver

        if release:
            tag = release["tag"]
            if old_tag and tag != old_tag:
                if important_release:
                    source_name = "Claude Code Changelog" if changelog_release else "GitHub Release"
                    f.write(f"\n🆕 **{source_name} 重要更新**: `{tag}`\n")
                    f.write(f"[查看详情]({release['url'] or RELEASES_URL})\n")
                    if release["published"]:
                        f.write(f"发布时间: {release['published'][:10]}\n")
                    summary = release_summary(release["body"])
                    if summary:
                        f.write(f"\n{summary}\n")
                    has_update = True
                    print(f"Claude Code 重要更新: {tag}")
                else:
                    print(f"忽略 Claude Code 普通/bugfix 更新: {tag}")
            else:
                print(f"Claude Code 最新版本: {tag}")
            state["github_tag"] = tag
            if changelog_release:
                state["changelog_source"] = changelog_release["source"]

        if not has_update:
            f.truncate(0)
            print("无重要功能更新，不写入晨报")

    state["last_check"] = datetime.now().isoformat()
    save_state(state)

if __name__ == "__main__":
    main()
