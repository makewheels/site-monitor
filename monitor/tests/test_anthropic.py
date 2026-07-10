from types import SimpleNamespace

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
