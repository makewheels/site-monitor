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
