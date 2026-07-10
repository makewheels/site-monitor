#!/usr/bin/env python3
"""检查 GitHub Copilot CLI Changelog 更新"""
import json
import urllib.request
import os
import re
from datetime import datetime
from .monitor_config import get_monitor_source, runtime_path

try:
    import feedparser
except ImportError:
    feedparser = None

STATE_FILE = runtime_path("state", "copilot_cli_state.json")
PENDING_FILE = runtime_path("pending", "copilot_cli_pending.txt")
SOURCE_CONFIG = get_monitor_source("github_copilot_cli_changelog")
ATOM_URL = SOURCE_CONFIG.get(
    "atom_url",
    "https://github.com/github/copilot-cli/commits/main/changelog.md.atom",
)
CHANGELOG_URL = SOURCE_CONFIG.get(
    "raw_url",
    "https://raw.githubusercontent.com/github/copilot-cli/main/changelog.md",
)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_version": None, "last_check": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_changelog():
    """获取 changelog 内容"""
    try:
        req = urllib.request.Request(CHANGELOG_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')
        return content
    except Exception as e:
        print(f"获取失败: {e}")
        return None

def fetch_atom_latest():
    """读取 GitHub changelog.md 的 Atom feed，判断 changelog 文件是否更新。"""
    if not feedparser:
        print("Atom 检查失败: 缺少 feedparser")
        return None

    try:
        req = urllib.request.Request(ATOM_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/atom+xml, application/xml, text/xml, */*',
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        feed = feedparser.parse(content)
        if not feed.entries:
            print("Atom 未返回条目")
            return None

        entry = feed.entries[0]
        title = (entry.get("title") or "").strip()
        version_match = re.search(r"version\s+([0-9]+(?:\.[0-9]+)+)", title, re.IGNORECASE)
        return {
            "id": entry.get("id") or entry.get("link") or title,
            "title": title,
            "updated": entry.get("updated", ""),
            "link": entry.get("link", ""),
            "version": version_match.group(1) if version_match else None,
        }
    except Exception as e:
        print(f"Atom 获取失败: {e}")
        return None

def extract_version_entries(content, target_version=None):
    """提取指定版本或最新版本的条目"""
    lines = content.split('\n')
    result = []
    current_version = None
    found_target = False
    
    for line in lines:
        if line.startswith('## '):
            # 解析版本号，如 "## 1.0.11 - 2026-03-23"
            version_line = line[3:].split(' - ')[0].strip()
            if current_version is None:
                current_version = version_line
                result.append(line)
            elif version_line != current_version:
                # 遇到下一个版本，停止
                break
        elif current_version:
            result.append(line)
    
    return current_version, '\n'.join(result)

def main():
    state = load_state()
    last_version = state.get("last_version")
    last_atom_id = state.get("last_atom_id")

    atom_latest = fetch_atom_latest()

    content = fetch_changelog()
    if not content:
        with open(PENDING_FILE, 'w') as f:
            f.write(f"## {datetime.now().strftime('%Y-%m-%d')} GitHub Copilot CLI\n\n")
            f.write("获取更新失败\n")
        return
    
    current_version, entries = extract_version_entries(content)
    
    if not current_version:
        print("无法解析版本号")
        return
    
    # 总是更新状态
    state["last_version"] = current_version
    if atom_latest:
        state["last_atom_id"] = atom_latest["id"]
        state["last_atom_updated"] = atom_latest["updated"]
        state["last_atom_title"] = atom_latest["title"]
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    # 总是写入汇报文件
    with open(PENDING_FILE, 'w') as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} GitHub Copilot CLI\n\n")
        atom_changed = bool(atom_latest and last_atom_id and atom_latest["id"] != last_atom_id)
        version_changed = bool(last_version and current_version != last_version)
        if version_changed or atom_changed:
            f.write(entries)
            print(f"发现新版本: {current_version}")
        else:
            f.write(f"无更新，当前版本: {current_version}\n")
            print(f"无更新，当前版本: {current_version}")

if __name__ == "__main__":
    main()
