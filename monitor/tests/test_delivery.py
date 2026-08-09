import json
import sys
import types
from pathlib import Path

from site_monitor import delivery


def test_delivery_disabled_by_env(monkeypatch):
    monkeypatch.setenv("SITE_MONITOR_SKIP_DELIVERY", "1")

    result = delivery.send_report("hello", {"enabled": True, "provider": "hermes_weixin"})

    assert result["skipped"] is True
    assert result["reason"] == "delivery_disabled"


def test_hermes_weixin_delivery_calls_send_tool(monkeypatch, tmp_path):
    calls = []

    fake_tool = types.ModuleType("tools.send_message_tool")
    fake_tool._handle_send = lambda args: calls.append(args) or json.dumps({"success": True})
    fake_tools = types.ModuleType("tools")
    monkeypatch.setitem(sys.modules, "tools", fake_tools)
    monkeypatch.setitem(sys.modules, "tools.send_message_tool", fake_tool)

    result = delivery.send_report(
        "hello",
        {
            "enabled": True,
            "provider": "hermes_weixin",
            "target": "weixin:filehelper",
            "hermes_home": str(tmp_path),
            "hermes_agent_path": str(tmp_path / "hermes-agent"),
        },
    )

    assert result["success"] is True
    assert calls == [{"target": "weixin:filehelper", "message": "hello"}]


def test_feishu_open_api_delivery(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        if url.endswith("/tenant_access_token/internal"):
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        return FakeResponse({"code": 0, "data": {"message_id": "m1"}})

    monkeypatch.setenv("FEISHU_APP_ID", "cli-test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("FEISHU_USER_ID", "ou-test")
    monkeypatch.setattr(delivery.requests, "post", fake_post)

    result = delivery.send_report(
        "# Daily report\n\nHello",
        {"enabled": True, "provider": "feishu", "markdown": True},
    )

    assert result == {"success": True, "provider": "feishu", "message_count": 1}
    assert calls[1]["params"] == {"receive_id_type": "open_id"}
    assert calls[1]["headers"] == {"Authorization": "Bearer tenant-token"}
    assert calls[1]["json"]["receive_id"] == "ou-test"
    assert calls[1]["json"]["msg_type"] == "interactive"
    card = json.loads(calls[1]["json"]["content"])
    assert card["elements"][0]["content"] == "# Daily report\n\nHello"


def test_feishu_structured_card_uses_trending_header_and_visible_urls(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(json)
        if url.endswith("/tenant_access_token/internal"):
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        return FakeResponse({"code": 0})

    monkeypatch.setenv("FEISHU_APP_ID", "cli-test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("FEISHU_USER_ID", "ou-test")
    monkeypatch.setattr(delivery.requests, "post", fake_post)
    payload = {
        "date": "2026-07-10",
        "items": [
            {
                "topic": "github_trending",
                "topic_name": "GitHub Trending",
                "status": "content",
                "entries": [
                    {
                        "title": "owner/project",
                        "summary": "Useful project",
                        "url": "https://monitor.example.com/projects/owner/project",
                        "intro_url": "https://monitor.example.com/projects/owner/project",
                        "source_url": "https://github.com/owner/project",
                    }
                ],
            },
            {
                "topic": "openai_news",
                "topic_name": "OpenAI News",
                "status": "content",
                "entries": [
                    {
                        "title": "新模型",
                        "translated_title": "新模型",
                        "original_title": "New model",
                        "summary": "文章介绍新模型的主要能力。",
                        "summary_zh": "文章介绍新模型的主要能力。",
                        "url": "https://openai.com/new-model",
                    }
                ],
            },
        ],
    }

    result = delivery.send_report(
        "fallback",
        {"enabled": True, "provider": "feishu", "markdown": True},
        payload=payload,
    )

    assert result["message_count"] == 1
    card = json.loads(calls[1]["content"])
    assert card["header"]["title"]["content"] == "🔥 今日 GitHub Trending · 1 个项目"
    markdown = "\n".join(
        element.get("content", "")
        for element in card["elements"]
        if element.get("tag") == "markdown"
    )
    assert "https://github.com/owner/project" in markdown
    assert "https://monitor.example.com/projects/owner/project" in markdown
    assert "手机项目解读" in markdown
    assert "OpenAI News" in markdown
    assert "原题：New model" in markdown
    assert "AI 摘要：文章介绍新模型的主要能力。" in markdown
    assert "https://openai.com/new-model" in markdown


def test_split_message_preserves_content():
    message = "first paragraph\n\nsecond paragraph"

    chunks = delivery._split_message(message, 18)

    assert chunks == ["first paragraph", "second paragraph"]


def test_fanout_cloud_api_posts_payload(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "stored": True}

    def fake_post(url, json, headers, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(delivery.requests, "post", fake_post)

    result = delivery.send_report(
        "hello",
        {
            "enabled": True,
            "providers": [
                {
                    "provider": "cloud_api",
                    "base_url": "https://monitor.example.com",
                    "upload_token": "secret",
                    "timeout": 3,
                }
            ],
        },
        payload={"report_id": "r1", "full_text": "hello"},
    )

    assert result["success"] is True
    assert calls == [
        {
            "url": "https://monitor.example.com/api/v1/reports",
            "json": {"report_id": "r1", "full_text": "hello"},
            "headers": {"X-Site-Monitor-Upload-Token": "secret"},
            "timeout": 3,
        }
    ]


def test_fanout_cloud_api_failure_is_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "runtime_path", lambda kind, name: str(tmp_path / name))

    def fake_post(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(delivery.requests, "post", fake_post)

    result = delivery.send_report(
        "hello",
        {
            "enabled": True,
            "providers": [
                {
                    "provider": "cloud_api",
                    "base_url": "https://monitor.example.com",
                    "upload_token": "secret",
                }
            ],
        },
        payload={"report_id": "r1", "full_text": "hello"},
    )

    assert result["success"] is False
    saved = list(Path(tmp_path / "cloud_sync").glob("*.json"))
    assert len(saved) == 1
