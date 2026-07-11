from types import SimpleNamespace
import json

from site_monitor import check_anthropic


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_fetch_via_rsshub_tries_fallback_instance(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        url = req.full_url
        calls.append(url)
        if "rsshub.app" in url:
            raise OSError("blocked")
        return FakeResponse(b"<rss></rss>")

    def fake_parse(content):
        return SimpleNamespace(
            entries=[
                {
                    "title": "Managed agents",
                    "link": "https://www.anthropic.com/engineering/managed-agents",
                    "published": "2026-05-01",
                }
            ]
        )

    monkeypatch.setattr(
        check_anthropic,
        "RSSHUB_URLS",
        [
            "https://rsshub.app/anthropic/engineering",
            "https://rsshub.ktachibana.party/anthropic/engineering",
        ],
    )
    monkeypatch.setattr(check_anthropic.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(check_anthropic.feedparser, "parse", fake_parse)

    articles = check_anthropic.fetch_via_rsshub()

    assert calls == [
        "https://rsshub.app/anthropic/engineering",
        "https://rsshub.ktachibana.party/anthropic/engineering",
    ]
    assert articles == [
        {
            "title": "Managed agents",
            "url": "https://www.anthropic.com/engineering/managed-agents",
            "published": "2026-05-01",
        }
    ]


def test_first_success_seeds_history_without_notifying(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    pending_file = tmp_path / "pending.txt"
    articles = [
        {
            "title": "Managed agents",
            "url": "https://www.anthropic.com/engineering/managed-agents",
            "published": "2026-05-01",
        }
    ]
    monkeypatch.setattr(check_anthropic, "STATE_FILE", str(state_file))
    monkeypatch.setattr(check_anthropic, "PENDING_FILE", str(pending_file))
    monkeypatch.setattr(check_anthropic, "fetch_articles", lambda: articles)

    check_anthropic.main()

    assert "首次成功抓取" in pending_file.read_text()
    assert "**Managed agents**" not in pending_file.read_text()
    state = json.loads(state_file.read_text())
    assert state["initialized"] is True
    assert state["known_articles"] == [articles[0]["url"]]
