import json
import sys
import types

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
