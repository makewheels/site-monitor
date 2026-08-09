from datetime import datetime

from site_monitor import weekly_trending


def test_build_weekly_payload_is_separate_from_daily():
    payload = weekly_trending.build_weekly_payload(
        [
            {
                "full_name": "owner/project",
                "zh_summary": "中文项目简介",
                "intro_url": "https://monitor.example.com/projects/owner/project",
                "source_url": "https://github.com/owner/project",
                "project_intro": {"problem": "解决问题"},
            }
        ],
        now=datetime.fromisoformat("2026-08-08T09:00:00+08:00"),
    )

    assert payload["report_id"] == "weekly-2026-W32"
    assert payload["items"][0]["topic"] == "github_trending_weekly"
    assert payload["items"][0]["entries"][0]["intro_url"].endswith("/owner/project")
    assert "本周 GitHub Trending" in payload["full_text"]


def test_main_sends_only_once_per_week(monkeypatch, tmp_path):
    sent = []
    monkeypatch.delenv("SITE_MONITOR_MONGO_URI", raising=False)
    monkeypatch.setattr(
        weekly_trending,
        "STATE_FILE",
        str(tmp_path / "weekly-state.json"),
    )
    monkeypatch.setattr(weekly_trending, "fetch_trending", lambda url: "<html>weekly</html>")
    monkeypatch.setattr(
        weekly_trending,
        "parse_trending",
        lambda html: [
            {
                "full_name": "owner/project",
                "url": "https://github.com/owner/project",
                "description": "A project",
            }
        ],
    )
    monkeypatch.setattr(
        weekly_trending,
        "apply_postprocessors",
        lambda source, payload: {
            "repos": [
                {
                    **payload["repos"][0],
                    "zh_summary": "中文简介",
                    "intro_url": "https://monitor.example.com/projects/owner/project",
                }
            ]
        },
    )
    monkeypatch.setattr(weekly_trending, "is_enabled", lambda: True)
    monkeypatch.setattr(
        weekly_trending,
        "send_report",
        lambda message, payload: sent.append(payload) or {"success": True, "provider": "feishu"},
    )

    assert weekly_trending.main() == 0
    assert weekly_trending.main() == 0

    assert len(sent) == 1
    assert sent[0]["items"][0]["topic"] == "github_trending_weekly"
