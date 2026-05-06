#!/usr/bin/env python3
"""检查 GitHub Copilot CLI Changelog 更新"""
import json
import urllib.request
import os
from datetime import datetime

STATE_FILE = os.path.expanduser("~/PythonProjects/site_monitor/copilot_cli_state.json")
PENDING_FILE = os.path.expanduser("~/PythonProjects/site_monitor/copilot_cli_pending.txt")
CHANGELOG_URL = "https://raw.githubusercontent.com/github/copilot-cli/main/changelog.md"

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
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    # 总是写入汇报文件
    with open(PENDING_FILE, 'w') as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} GitHub Copilot CLI\n\n")
        if last_version and current_version != last_version:
            f.write(entries)
            print(f"发现新版本: {current_version}")
        else:
            f.write(f"无更新，当前版本: {current_version}\n")
            print(f"无更新，当前版本: {current_version}")

if __name__ == "__main__":
    main()