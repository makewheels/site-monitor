import json
from types import SimpleNamespace

from site_monitor import check_rss_feeds


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def _entry(title, link, published="2026-07-08"):
    return {"title": title, "link": link, "published": published}


def _patch_runtime(tmp_path, monkeypatch):
    def fake_runtime_path(kind, filename):
        d = tmp_path / kind
        d.mkdir(parents=True, exist_ok=True)
        return str(d / filename)
    monkeypatch.setattr(check_rss_feeds, "runtime_path", fake_runtime_path)


def test_fetch_feed_falls_back_to_second_url(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        url = req.full_url
        calls.append(url)
        if "primary" in url:
            raise OSError("blocked")
        return FakeResponse(b"<rss></rss>")

    def fake_parse(content):
        return SimpleNamespace(entries=[_entry("Eval post", "https://example.com/eval")])

    monkeypatch.setattr(check_rss_feeds.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(check_rss_feeds.feedparser, "parse", fake_parse)

    articles = check_rss_feeds.fetch_feed([
        "https://primary.example.com/feed",
        "https://fallback.example.com/feed",
    ])

    assert calls == [
        "https://primary.example.com/feed",
        "https://fallback.example.com/feed",
    ]
    assert articles == [
        {"title": "Eval post", "url": "https://example.com/eval", "published": "2026-07-08"}
    ]


def test_run_feed_first_run_records_without_notifying(monkeypatch, tmp_path):
    _patch_runtime(tmp_path, monkeypatch)

    articles = [
        {"title": f"Old {i}", "url": f"https://example.com/old{i}", "published": "2026-07-01"}
        for i in range(3)
    ]
    monkeypatch.setattr(check_rss_feeds, "fetch_feed", lambda urls: articles)

    check_rss_feeds.run_feed(
        {"key": "metr", "name": "METR", "urls": ["https://metr.org/feed.xml"]}
    )

    pending = (tmp_path / "pending" / "metr_pending.txt").read_text()
    assert "首次运行" in pending
    assert "Old 0" not in pending  # 历史文章不进通知

    state = json.loads((tmp_path / "state" / "metr_state.json").read_text())
    assert len(state["known_urls"]) == 3


def test_run_feed_subsequent_run_notifies_only_new(monkeypatch, tmp_path):
    _patch_runtime(tmp_path, monkeypatch)

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "swe_bench_state.json").write_text(json.dumps({
        "known_urls": ["https://example.com/old"],
        "last_check": "2026-07-07T00:00:00",
    }))

    monkeypatch.setattr(check_rss_feeds, "fetch_feed", lambda urls: [
        {"title": "Old", "url": "https://example.com/old", "published": "2026-07-07"},
        {"title": "New release", "url": "https://example.com/new", "published": "2026-07-08"},
    ])

    check_rss_feeds.run_feed({"key": "swe_bench", "name": "SWE-bench", "urls": ["x"]})

    pending = (tmp_path / "pending" / "swe_bench_pending.txt").read_text()
    assert "发现 1 篇新文章" in pending
    assert "New release" in pending
    assert "- [Old]" not in pending
