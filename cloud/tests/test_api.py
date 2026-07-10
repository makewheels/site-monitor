from site_monitor_cloud.api import create_app, newest_per_date


class FakeStore:
    def __init__(self):
        self.payloads = {}

    def upsert_report(self, payload):
        self.payloads[payload["report_id"]] = payload
        return {"report_id": payload["report_id"], "item_count": len(payload.get("items", []))}

    def latest(self):
        if not self.payloads:
            return None
        return list(self.payloads.values())[-1]

    def list_reports(self, limit=30, topic=None):
        values = list(self.payloads.values())[:limit]
        if not topic:
            return values
        return [
            item
            for payload in values
            for item in payload.get("items", [])
            if item.get("topic") == topic
        ]

    def detail(self, report_id):
        return self.payloads.get(report_id)

    def topics(self):
        return [{"key": "claude_code", "name": "Claude Code", "order": 50}]


def test_upload_and_read_latest_report(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_UPLOAD_TOKEN", "upload-token")
    monkeypatch.setenv("SITE_MONITOR_APP_TOKEN", "app-token")
    app = create_app(FakeStore())
    client = app.test_client()

    payload = {
        "report_id": "2026-05-18-test",
        "date": "2026-05-18",
        "items": [{"topic": "claude_code", "title": "Claude Code"}],
    }

    upload = client.post(
        "/api/v1/reports",
        json=payload,
        headers={"X-Site-Monitor-Upload-Token": "upload-token"},
    )
    assert upload.status_code == 200
    assert upload.get_json()["item_count"] == 1

    latest = client.get(
        "/api/v1/reports/latest",
        headers={"X-Site-Monitor-App-Token": "app-token"},
    )
    assert latest.status_code == 200
    assert latest.get_json()["report_id"] == "2026-05-18-test"


def test_api_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_UPLOAD_TOKEN", "upload-token")
    app = create_app(FakeStore())
    client = app.test_client()

    response = client.post("/api/v1/reports", json={"report_id": "x"})

    assert response.status_code == 401


def test_latest_app_release_uses_environment_config(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_APP_TOKEN", "app-token")
    monkeypatch.setenv("SITE_MONITOR_ANDROID_VERSION_CODE", "2")
    monkeypatch.setenv("SITE_MONITOR_ANDROID_VERSION_NAME", "0.2.0")
    monkeypatch.setenv("SITE_MONITOR_ANDROID_APK_URL", "https://example.com/ai-monitor.apk")
    monkeypatch.setenv("SITE_MONITOR_ANDROID_APK_SHA256", "abc123")
    monkeypatch.setenv("SITE_MONITOR_ANDROID_RELEASE_NOTES", "新增栏目历史")
    app = create_app(FakeStore())
    client = app.test_client()

    response = client.get(
        "/api/v1/app/releases/latest",
        headers={"X-Site-Monitor-App-Token": "app-token"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "version_code": 2,
        "version_name": "0.2.0",
        "apk_url": "https://example.com/ai-monitor.apk",
        "sha256": "abc123",
        "release_notes": "新增栏目历史",
        "force_update": False,
    }


def test_newest_per_date_removes_daily_demo_duplicates():
    documents = [
        {"date": "2026-07-11", "report_id": "latest"},
        {"date": "2026-07-11", "report_id": "older-demo"},
        {"date": "2026-07-10", "report_id": "previous-day"},
        {"date": "2026-07-09", "report_id": "outside-limit"},
    ]

    assert newest_per_date(documents, limit=2) == [
        {"date": "2026-07-11", "report_id": "latest"},
        {"date": "2026-07-10", "report_id": "previous-day"},
    ]
