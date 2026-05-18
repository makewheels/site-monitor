from site_monitor.cloud_api import create_app


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
