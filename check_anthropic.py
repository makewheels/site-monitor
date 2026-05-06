#!/usr/bin/env python3
"""检查 Anthropic Engineering 新文章"""
import json
import urllib.request
import re
import os
from datetime import datetime

STATE_FILE = os.path.expanduser("~/PythonProjects/site_monitor/anthropic_state.json")
PENDING_FILE = os.path.expanduser("~/PythonProjects/site_monitor/anthropic_pending.txt")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"known_articles": []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_articles():
    """获取最新文章列表"""
    url = "https://www.anthropic.com/engineering"
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8')
        
        # 提取所有 engineering 文章链接
        hrefs = re.findall(r'href="(/engineering/[^"]+)"', html)
        
        articles = []
        seen = set()
        for href in hrefs:
            full_url = 'https://www.anthropic.com' + href
            if full_url not in seen:
                seen.add(full_url)
                # 从 URL 提取标题（去掉前缀）
                slug = href.replace('/engineering/', '').replace('-', ' ').title()
                articles.append({"title": slug, "url": full_url})
        
        return articles[:20]
    except Exception as e:
        print(f"获取失败: {e}")
        return []

def main():
    state = load_state()
    known = set(state["known_articles"])
    
    articles = fetch_articles()
    new_articles = []
    
    for article in articles:
        if article["url"] not in known:
            new_articles.append(article)
    
    # 总是更新状态
    if articles:
        state["known_articles"] = [a["url"] for a in articles]
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    # 总是写入汇报文件
    with open(PENDING_FILE, 'w') as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} Anthropic Engineering\n\n")
        if new_articles:
            f.write(f"发现 {len(new_articles)} 篇新文章:\n\n")
            for a in new_articles:
                f.write(f"- [{a['title']}]({a['url']})\n")
            print(f"发现 {len(new_articles)} 篇新文章:")
            for a in new_articles:
                print(f"  - {a['title']}")
        else:
            f.write("今日无新文章\n")
            print("无新文章")

if __name__ == "__main__":
    main()