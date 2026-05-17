#!/usr/bin/env python3
"""检查 LangChain 博客新文章（优先用 RSS）"""
import json
import urllib.request
import re
import os
from datetime import datetime

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

STATE_FILE = os.path.expanduser("~/PythonProjects/site_monitor/langchain_blog_state.json")
PENDING_FILE = os.path.expanduser("~/PythonProjects/site_monitor/langchain_blog_pending.txt")
FEED_URLS = [
    "https://blog.langchain.dev/rss",
    "https://blog.langchain.dev/feed/",
    "https://blog.langchain.dev/atom.xml",
]
BLOG_URL = "https://blog.langchain.dev/"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"known_urls": [], "last_check": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_via_rss():
    """尝试 RSS/Atom feed"""
    if not feedparser:
        return None

    for feed_url in FEED_URLS:
        try:
            req = urllib.request.Request(feed_url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            if feed.entries:
                articles = []
                for e in feed.entries:
                    articles.append({
                        "title": e.get("title", "Untitled"),
                        "url": e.get("link", ""),
                        "published": e.get("published", ""),
                    })
                return articles
        except Exception as e:
            print(f"  RSS {feed_url} 失败: {e}")
            continue
    return None

def fetch_via_scrape():
    """回退：爬取博客首页"""
    if not BeautifulSoup:
        return []

    try:
        req = urllib.request.Request(BLOG_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8')

        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        seen = set()

        for article in soup.find_all(["article", "h2", "h3"]):
            link = article.find("a") if article.name != "a" else article
            if not link:
                continue
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 5:
                continue
            if href not in seen:
                seen.add(href)
                articles.append({"title": title, "url": href})

        return articles[:20]
    except Exception as e:
        print(f"  爬取失败: {e}")
        return []

def main():
    state = load_state()
    known = set(state["known_urls"])

    # 优先 RSS
    articles = fetch_via_rss()
    if not articles:
        print("RSS 不可用，回退到爬取...")
        articles = fetch_via_scrape()

    new_articles = []
    for article in articles:
        if article["url"] not in known:
            new_articles.append(article)

    if articles:
        state["known_urls"] = [a["url"] for a in articles]
    state["last_check"] = datetime.now().isoformat()
    save_state(state)

    with open(PENDING_FILE, 'w') as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} LangChain Blog\n\n")
        if new_articles:
            f.write(f"发现 {len(new_articles)} 篇新文章:\n\n")
            for a in new_articles:
                pub = f" ({a.get('published', '')[:10]})" if a.get('published') else ""
                f.write(f"- [{a['title']}]({a['url']}){pub}\n")
            print(f"发现 {len(new_articles)} 篇新文章:")
            for a in new_articles:
                print(f"  - {a['title']}")
        else:
            if articles:
                f.write(f"今日无新文章（追踪 {len(articles)} 篇）\n")
                print("无新文章")
            else:
                f.write("无法获取文章列表\n")
                print("无法获取文章列表")

if __name__ == "__main__":
    main()
