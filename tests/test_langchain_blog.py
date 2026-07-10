import json

from site_monitor import check_langchain_blog


def test_first_success_seeds_history_without_reporting_every_article(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    pending_file = tmp_path / "pending.txt"
    articles = [
        {
            "title": "New LangChain article",
            "url": "https://www.langchain.com/blog/new-article",
            "published": "Thu, 09 Jul 2026 16:20:31 GMT",
        }
    ]
    monkeypatch.setattr(check_langchain_blog, "STATE_FILE", str(state_file))
    monkeypatch.setattr(check_langchain_blog, "PENDING_FILE", str(pending_file))
    monkeypatch.setattr(check_langchain_blog, "fetch_via_rss", lambda: articles)

    check_langchain_blog.main()

    assert "首次成功抓取" in pending_file.read_text()
    assert "New LangChain article" not in pending_file.read_text()
    state = json.loads(state_file.read_text())
    assert state["initialized"] is True
    assert state["known_urls"] == [articles[0]["url"]]


def test_later_run_reports_only_new_articles(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    pending_file = tmp_path / "pending.txt"
    state_file.write_text(
        json.dumps(
            {
                "initialized": True,
                "known_urls": ["https://www.langchain.com/blog/old-article"],
            }
        )
    )
    articles = [
        {
            "title": "New LangChain article",
            "url": "https://www.langchain.com/blog/new-article",
            "published": "Thu, 09 Jul 2026 16:20:31 GMT",
        }
    ]
    monkeypatch.setattr(check_langchain_blog, "STATE_FILE", str(state_file))
    monkeypatch.setattr(check_langchain_blog, "PENDING_FILE", str(pending_file))
    monkeypatch.setattr(check_langchain_blog, "fetch_via_rss", lambda: articles)

    check_langchain_blog.main()

    content = pending_file.read_text()
    assert "发现 1 篇新文章" in content
    assert "New LangChain article" in content
