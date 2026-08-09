from site_monitor import codex_radar


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


OPEN_PAGE = b"""
<html><body>
  <section class="site-announcement" data-speed-window="open">
    <strong class="site-announcement-headline">Current window open</strong>
    <p>Reset confirmed.</p>
    <a class="site-announcement-source" href="https://example.com/source">source</a>
  </section>
  <section>
    <span class="window-source-kicker">Speed window open</span>
    <strong class="window-source-title">Official reset notice</strong>
    <div class="window-time-card"><span>Notice</span><b>09:00</b></div>
    <div class="window-source-evidence"><span>Evidence</span><strong>Reset Monday</strong></div>
  </section>
</body></html>
"""


def test_fetch_page_event_builds_stable_open_signature(monkeypatch):
    monkeypatch.setattr(
        codex_radar.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(OPEN_PAGE),
    )

    first = codex_radar.fetch_page_event()
    second = codex_radar.fetch_page_event()

    assert first == second
    assert first["window_state"] == "open"
    assert first["guid"].startswith("page-status:")
    assert first["link"] == "https://example.com/source"
    assert "Reset confirmed" in first["summary"]


def test_main_sends_changed_open_page_once(monkeypatch, tmp_path):
    state_file = tmp_path / "codex_radar_state.json"
    state_file.write_text(
        '{"known_guids": ["old-entry"], "last_check": "before"}',
        encoding="utf-8",
    )
    sent = []
    saved = []
    page_event = {
        "title": "当前窗口已开启 · 官方重置预告",
        "link": "https://example.com/reset",
        "guid": "page-status:new",
        "published": "",
        "summary": "官方已确认",
        "window_state": "open",
    }

    monkeypatch.delenv("SITE_MONITOR_MONGO_URI", raising=False)
    monkeypatch.setattr(codex_radar, "STATE_FILE", str(state_file))
    monkeypatch.setattr(codex_radar, "fetch_feed", lambda: [])
    monkeypatch.setattr(codex_radar, "fetch_page_event", lambda: dict(page_event))
    monkeypatch.setattr(codex_radar, "is_enabled", lambda: True)
    monkeypatch.setattr(
        codex_radar,
        "send_report",
        lambda message, payload: sent.append(message) or {"success": True, "provider": "feishu"},
    )

    assert codex_radar.main() == 0
    saved.append(codex_radar.load_state())
    assert codex_radar.main() == 0

    assert len(sent) == 1
    assert "当前窗口已开启" in sent[0]
    assert saved[0]["page_signature"] == "page-status:new"
    assert codex_radar.load_state()["page_window_state"] == "open"
