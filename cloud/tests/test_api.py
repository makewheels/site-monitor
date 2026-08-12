from site_monitor_cloud.api import MongoReportStore, create_app, newest_per_date


class RecordingCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))


class FakeStore:
    def __init__(self):
        self.payloads = {}
        self.project_intros = {}

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
        return [{"key": "openai_news", "name": "OpenAI News", "order": 30}]

    def project_intro(self, owner, repo):
        return self.project_intros.get(f"{owner}/{repo}".lower())


def test_upload_and_read_latest_report(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_UPLOAD_TOKEN", "upload-token")
    monkeypatch.setenv("SITE_MONITOR_APP_TOKEN", "app-token")
    app = create_app(FakeStore())
    client = app.test_client()

    payload = {
        "report_id": "2026-05-18-test",
        "date": "2026-05-18",
        "items": [{"topic": "openai_news", "title": "OpenAI News"}],
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


def test_web_app_and_assets_are_served_without_embedding_token(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_APP_TOKEN", "do-not-embed-this-token")
    app = create_app(FakeStore())
    client = app.test_client()

    page = client.get("/")
    script = client.get("/web/assets/app.js")

    assert page.status_code == 200
    assert page.content_type.startswith("text/html")
    assert b"AI \xe6\x97\xa5\xe6\x8a\xa5" in page.data
    assert b"do-not-embed-this-token" not in page.data
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert script.status_code == 200
    assert script.content_type.startswith(("text/javascript", "application/javascript"))
    assert b"do-not-embed-this-token" not in script.data


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


def test_cloud_upsert_records_article_content_count():
    store = object.__new__(MongoReportStore)
    store.reports = RecordingCollection()
    store.items = RecordingCollection()
    store.project_intros = RecordingCollection()

    store.upsert_report(
        {
            "report_id": "2026-07-11-test",
            "items": [
                {
                    "topic": "langchain_blog",
                    "entries": [
                        {
                            "translated_title": "译文",
                            "summary_zh": "摘要",
                            "url": "https://example.com/article",
                        }
                    ],
                },
                {"topic": "openai_news", "entries": []},
            ],
        }
    )

    report_doc = store.reports.calls[0][1]["$set"]
    assert report_doc["content_count"] == 1
    assert report_doc["content_item_count"] == 1
    assert store.items.calls[0][1]["$set"]["entry_count"] == 1
    assert store.items.calls[1][1]["$set"]["entry_count"] == 0


def test_project_page_is_public_mobile_slide_deck_and_escapes_content():
    store = FakeStore()
    store.project_intros["owner/project"] = {
        "full_name": "owner/project",
        "title": "Project <unsafe>",
        "tagline": "项目一句话简介",
        "problem": "解决复杂任务",
        "architecture": [{"name": "Core", "description": "处理任务"}],
        "audience": ["平台工程师"],
        "workflow": [{"name": "输入", "description": "读取任务"}],
        "core_concepts": [{"name": "调度器", "description": "编排执行"}],
        "alternatives": [
            {"name": "脚本", "when_choose": "一次性任务", "tradeoff": "缺少治理"}
        ],
        "questions": ["是否支持自托管？"],
        "why_choose": ["需要自动化"],
        "avoid_when": ["只需简单脚本"],
        "use_cases": ["研究", "开发", "评测"],
        "getting_started": ["阅读 README"],
        "risks": ["需要审查"],
        "facts": {"stars": 1234, "language": "Python", "license": "MIT", "pushed_at": "2026-08-09"},
        "source_urls": ["https://github.com/owner/project"],
    }
    app = create_app(store)
    client = app.test_client()

    response = client.get("/projects/owner/project")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert b"scroll-snap-type:y mandatory" in response.data
    assert b"Project &lt;unsafe&gt;" in response.data
    assert b"Project <unsafe>" not in response.data
    assert b"GitHub" in response.data
    assert "端到端工作流".encode() in response.data
    assert "同类方案怎么取舍".encode() in response.data
    assert b"site-moitor-api" not in response.data
    assert response.headers["Cache-Control"] == "public, max-age=300"


def test_project_page_returns_404_when_not_generated():
    app = create_app(FakeStore())
    response = app.test_client().get("/projects/owner/missing")

    assert response.status_code == 404
