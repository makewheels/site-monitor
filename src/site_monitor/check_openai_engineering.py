#!/usr/bin/env python3
"""检查 OpenAI Engineering 博客新文章"""
import json
import urllib.request
import re
import os
from datetime import datetime
from .monitor_config import runtime_path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

STATE_FILE = runtime_path("state", "openai_engineering_state.json")
PENDING_FILE = runtime_path("pending", "openai_engineering_pending.txt")
BLOG_URLS = [
    "https://openai.com/blog/engineering/",
    "https://openai.com/index/engineering/",
    "https://openai.com/blog/?tag=engineering",
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"known_articles": [], "last_check": None}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_articles():
    """尝试多个 URL 获取 engineering 文章"""
    for url in BLOG_URLS:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8')

            if BeautifulSoup:
                soup = BeautifulSoup(html, 'html.parser')
                articles = []
                seen = set()

                # 找所有带 engineering 的文章链接
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True)
                    if not text or len(text) < 5:
                        continue
                    if 'engineering' in href.lower():
                        full_url = href if href.startswith('http') else f"https://openai.com{href}"
                        if full_url not in seen:
                            seen.add(full_url)
                            articles.append({"title": text, "url": full_url})

                if articles:
                    return articles[:20]

            # fallback: regex
            pattern = r'href="(/[^"]*engineering[^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.IGNORECASE)
            articles = []
            seen = set()
            for href, text in matches:
                full_url = f"https://openai.com{href}"
                if full_url not in seen:
                    seen.add(full_url)
                    articles.append({"title": text.strip(), "url": full_url})
            if articles:
                return articles[:20]

        except Exception as e:
            print(f"  {url} 失败: {e}")
            continue

    return []

def main():
    state = load_state()
    known = set(state["known_articles"])
    
    articles = fetch_articles()
    new_articles = []
    
    for article in articles:
        if article["url"] not in known:
            new_articles.append(article)
    
    if articles:
        state["known_articles"] = [a["url"] for a in articles]
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    with open(PENDING_FILE, 'w') as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} OpenAI Engineering\n\n")
        if new_articles:
            f.write(f"发现 {len(new_articles)} 篇新文章:\n\n")
            for a in new_articles:
                f.write(f"- [{a['title']}]({a['url']})\n")
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
