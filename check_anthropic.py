#!/usr/bin/env python3
"""检查 Anthropic Engineering 新文章（优先使用 RSSHub）"""
import json
import urllib.request
import re
import os
from datetime import datetime
from monitor_config import get_monitor_source

try:
    import feedparser
except ImportError:
    feedparser = None

STATE_FILE = os.path.expanduser("~/PythonProjects/site_monitor/anthropic_state.json")
PENDING_FILE = os.path.expanduser("~/PythonProjects/site_monitor/anthropic_pending.txt")
SOURCE_CONFIG = get_monitor_source("anthropic_engineering")
RSSHUB_URLS = SOURCE_CONFIG.get("rsshub_urls") or [
    "https://rsshub.app/anthropic/engineering",
    "https://rsshub.ktachibana.party/anthropic/engineering",
]
ENGINEERING_URL = SOURCE_CONFIG.get("fallback_url", "https://www.anthropic.com/engineering")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"known_articles": []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_via_rsshub():
    """通过 RSSHub 获取最新文章列表。"""
    if not feedparser:
        print("RSSHub 解析失败: 缺少 feedparser")
        return []

    for rsshub_url in RSSHUB_URLS:
        try:
            req = urllib.request.Request(rsshub_url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()

            feed = feedparser.parse(content)
            articles = []
            for entry in feed.entries[:20]:
                url = entry.get("link", "")
                title = entry.get("title", "").strip() or url
                if url:
                    articles.append({
                        "title": title,
                        "url": url,
                        "published": entry.get("published", ""),
                    })

            if articles:
                print(f"RSSHub 获取成功: {rsshub_url} ({len(articles)} 篇)")
                return articles
            print(f"RSSHub 未返回文章: {rsshub_url}")
        except Exception as e:
            print(f"RSSHub 获取失败: {rsshub_url}: {e}")
    return []

def fetch_via_scrape():
    """回退：直接解析 Anthropic Engineering 页面。"""
    try:
        req = urllib.request.Request(ENGINEERING_URL, headers={
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
        print(f"网页解析失败: {e}")
        return []

def fetch_articles():
    """获取最新文章列表：优先 RSSHub，失败时回退到网页解析。"""
    articles = fetch_via_rsshub()
    if articles:
        return articles

    print("RSSHub 不可用，回退到 Anthropic 页面解析")
    return fetch_via_scrape()

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
                pub = f" ({a.get('published', '')[:10]})" if a.get("published") else ""
                f.write(f"- [{a['title']}]({a['url']}){pub}\n")
            print(f"发现 {len(new_articles)} 篇新文章:")
            for a in new_articles:
                print(f"  - {a['title']}")
        else:
            f.write("今日无新文章\n")
            print("无新文章")

if __name__ == "__main__":
    main()
