from types import SimpleNamespace

from site_monitor import check_copilot_cli


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_extract_version_entries_returns_latest_block():
    content = """## 1.0.48 - 2026-05-14

- New pricing display
- CJK rendering fix

## 1.0.47 - 2026-05-13

- Older item
"""

    version, entries = check_copilot_cli.extract_version_entries(content)

    assert version == "1.0.48"
    assert "New pricing display" in entries
    assert "1.0.47" not in entries


def test_fetch_atom_latest_parses_version(monkeypatch):
    def fake_urlopen(req, timeout):
        return FakeResponse(b"<feed></feed>")

    def fake_parse(content):
        return SimpleNamespace(
            entries=[
                {
                    "id": "commit-123",
                    "title": "Update changelog.md for version 1.0.49",
                    "updated": "2026-05-17T01:00:00Z",
                    "link": "https://github.com/github/copilot-cli/commit/123",
                }
            ]
        )

    monkeypatch.setattr(check_copilot_cli.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(check_copilot_cli.feedparser, "parse", fake_parse)

    latest = check_copilot_cli.fetch_atom_latest()

    assert latest["id"] == "commit-123"
    assert latest["version"] == "1.0.49"
    assert latest["updated"] == "2026-05-17T01:00:00Z"
