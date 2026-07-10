from site_monitor.cloud_api import MongoReportStore, create_app


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


class FakeStateCollection:
    def __init__(self, documents=None):
        self.documents = {doc["filename"]: doc for doc in (documents or [])}

    def find(self, *args, **kwargs):
        return list(self.documents.values())

    def update_one(self, query, update, upsert=False):
        filename = query["filename"]
        current = self.documents.setdefault(filename, {"filename": filename})
        current.update(update.get("$setOnInsert", {}))
        current.update(update.get("$set", {}))


def test_monitor_state_round_trip(tmp_path):
    collection = FakeStateCollection(
        [
            {"filename": "anthropic_state.json", "data": {"known_articles": ["a"]}},
            {"filename": "../unsafe.json", "data": {"ignored": True}},
        ]
    )
    store = object.__new__(MongoReportStore)
    store.monitor_state = collection

    restored = store.restore_monitor_state(tmp_path)
    assert restored == 1
    assert (tmp_path / "anthropic_state.json").read_text()
    assert not (tmp_path.parent / "unsafe.json").exists()

    (tmp_path / "github_state.json").write_text('{"repos": ["r1"]}')
    saved = store.save_monitor_state(tmp_path)

    assert saved == 2
    assert collection.documents["github_state.json"]["data"] == {"repos": ["r1"]}
