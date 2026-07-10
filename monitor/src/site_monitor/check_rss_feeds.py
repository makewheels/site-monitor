#!/usr/bin/env python3
"""通用 RSS/Atom 监控。

从 config.json 的 rss_feeds 列表读取订阅源,逐个抓取新文章并写入 pending 文件。
优先 RSS/Atom;首次运行只记录已有文章,不当作新文章通知,避免首日报表刷屏。
"""
import json
import os
import urllib.request
from datetime import datetime

from .monitor_config import get_rss_feeds, runtime_path

try:
    import feedparser
except ImportError:
    feedparser = None


def _state_file(key):
    return runtime_path("state", f"{key}_state.json")


def load_state(key):
    state_file = _state_file(key)
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
    return {"known_urls": [], "last_check": None}


def save_state(key, state):
    with open(_state_file(key), "w") as f:
        json.dump(state, f, indent=2)


def fetch_feed(urls):
    """依次尝试 urls,返回第一组成功解析的文章列表;全部失败返回 []。"""
    if not feedparser:
        print("RSS 解析失败: 缺少 feedparser")
        return []

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            if feed.entries:
                articles = []
                for e in feed.entries:
                    link = e.get("link", "")
                    if not link:
                        continue
                    articles.append({
                        "title": e.get("title", "").strip() or link,
                        "url": link,
                        "published": e.get("published", e.get("updated", "")),
                    })
                print(f"RSS 获取成功: {url} ({len(articles)} 篇)")
                return articles
            print(f"RSS 未返回文章: {url}")
        except Exception as e:
            print(f"RSS 获取失败: {url}: {e}")
    return []


def run_feed(feed):
    key = feed["key"]
    name = feed.get("name", key)
    urls = feed.get("urls") or []
    limit = feed.get("limit", 20)

    first_run = not os.path.exists(_state_file(key))
    articles = fetch_feed(urls)[:limit]

    state = load_state(key)
    known = set(state.get("known_urls", []))
    new_articles = [a for a in articles if a["url"] not in known]

    if articles:
        state["known_urls"] = [a["url"] for a in articles]
    state["last_check"] = datetime.now().isoformat()
    save_state(key, state)

    pending_file = runtime_path("pending", f"{key}_pending.txt")
    with open(pending_file, "w") as f:
        f.write(f"## {datetime.now().strftime('%Y-%m-%d')} {name}\n\n")
        if first_run and articles:
            f.write(f"首次运行,已记录 {len(articles)} 篇(不通知历史文章)\n")
            print(f"[{name}] 首次运行,记录 {len(articles)} 篇")
        elif new_articles:
            f.write(f"发现 {len(new_articles)} 篇新文章:\n\n")
            for index, a in enumerate(new_articles):
                if index:
                    f.write("\n---\n\n")
                f.write(f"**{a['title']}**\n")
                if a.get("published"):
                    f.write(f"📅 {a['published'][:10]}\n")
                f.write(f"🔗 {a['url']}\n")
            print(f"[{name}] 发现 {len(new_articles)} 篇新文章")
        elif articles:
            f.write(f"今日无新文章(追踪 {len(articles)} 篇)\n")
            print(f"[{name}] 无新文章")
        else:
            f.write("无法获取文章列表\n")
            print(f"[{name}] 无法获取文章列表")


def main():
    feeds = get_rss_feeds()
    if not feeds:
        print("config.json 未配置 rss_feeds")
        return
    for feed in feeds:
        run_feed(feed)


if __name__ == "__main__":
    main()
