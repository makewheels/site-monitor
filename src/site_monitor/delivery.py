"""Delivery backends for site-monitor reports."""
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from .monitor_config import load_config


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_delivery_config() -> dict[str, Any]:
    return load_config().get("delivery", {})


def is_enabled(config: dict[str, Any] | None = None) -> bool:
    config = config or get_delivery_config()
    if os.getenv("SITE_MONITOR_SKIP_DELIVERY", "").lower() in {"1", "true", "yes"}:
        return False
    return bool(config.get("enabled", False))


def send_report(message: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or get_delivery_config()
    if not is_enabled(config):
        return {"success": True, "skipped": True, "reason": "delivery_disabled"}

    provider = config.get("provider")
    if provider != "hermes_weixin":
        raise ValueError(f"Unsupported delivery provider: {provider}")
    return _send_via_hermes_weixin(message, config)


def _send_via_hermes_weixin(message: str, config: dict[str, Any]) -> dict[str, Any]:
    target = config.get("target", "")
    if not target:
        raise ValueError("delivery.target is required")

    hermes_home = Path(config.get("hermes_home") or Path.home() / ".hermes")
    hermes_agent_path = Path(config.get("hermes_agent_path") or hermes_home / "hermes-agent")
    os.environ.setdefault("HERMES_HOME", str(hermes_home))
    _load_env_file(hermes_home / ".env")

    if str(hermes_agent_path) not in sys.path:
        sys.path.insert(0, str(hermes_agent_path))

    noise = io.StringIO()
    with contextlib.redirect_stdout(noise):
        from tools.send_message_tool import _handle_send
        raw_result = _handle_send({"target": target, "message": message})
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Hermes send returned non-JSON result: {raw_result}") from exc

    if result.get("error"):
        raise RuntimeError(result["error"])
    return result
