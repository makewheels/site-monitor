"""Delivery backends for site-monitor reports."""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime

import time
import requests
from .monitor_config import load_config
from .monitor_config import runtime_path
from .monitor_config import PROJECT_ROOT


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


def send_report(
    message: str,
    config: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or get_delivery_config()
    if not is_enabled(config):
        return {"success": True, "skipped": True, "reason": "delivery_disabled"}

    providers = config.get("providers")
    if providers:
        return _send_fanout(message, payload or {"full_text": message}, providers)

    provider = config.get("provider")
    return _send_provider(provider, message, payload or {"full_text": message}, config)


def _send_fanout(
    message: str,
    payload: dict[str, Any],
    providers: list[dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for provider_config in providers:
        if provider_config.get("enabled", True) is False:
            results.append(
                {
                    "provider": provider_config.get("provider", "unknown"),
                    "success": True,
                    "skipped": True,
                    "reason": "provider_disabled",
                }
            )
            continue
        provider = provider_config.get("provider")
        try:
            result = _send_provider(provider, message, payload, provider_config)
            result.setdefault("provider", provider)
            result.setdefault("success", True)
            results.append(result)
        except Exception as exc:
            failure = {
                "provider": provider,
                "success": False,
                "error": str(exc),
            }
            if provider == "cloud_api":
                _save_cloud_sync_failure(payload, provider_config, str(exc))
            results.append(failure)

    return {
        "success": all(result.get("success", False) for result in results),
        "results": results,
    }


def _send_provider(
    provider: str | None,
    message: str,
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    if provider == "hermes_weixin":
        return _send_via_hermes_weixin(message, config)
    if provider == "feishu":
        return _send_via_feishu(message, config)
    if provider == "cloud_api":
        return _send_via_cloud_api(payload, config)
    raise ValueError(f"Unsupported delivery provider: {provider}")


def _send_via_feishu(message: str, config: dict[str, Any]) -> dict[str, Any]:
    """通过 lark-cli 把报告发到飞书。优先私聊(FEISHU_USER_ID),否则发群(FEISHU_CHAT_ID)。
    凭证走 .env,不进 config。"""
    _load_env_file(PROJECT_ROOT / ".env")
    cli = config.get("lark_cli") or os.getenv("LARK_CLI", "lark-cli")
    user_id = config.get("user_id") or os.getenv("FEISHU_USER_ID", "")
    chat_id = config.get("chat_id") or os.getenv("FEISHU_CHAT_ID", "")
    if not Path(cli).exists():
        raise ValueError(f"lark-cli 不存在: {cli}")
    if user_id:
        target_args = ["--user-id", user_id]
    elif chat_id:
        target_args = ["--chat-id", chat_id]
    else:
        raise ValueError("FEISHU_USER_ID 或 FEISHU_CHAT_ID 未配置(写 site_monitor/.env)")

    env = dict(os.environ)
    env["PATH"] = env.get("PATH", "") + ":" + str(Path(cli).parent)
    env.pop("HERMES_HOME", None)
    flag = "--markdown" if config.get("markdown", True) else "--text"

    last = ""
    for attempt in range(3):
        try:
            r = subprocess.run(
                [cli, "im", "+messages-send", "--as", "bot",
                 *target_args, flag, message],
                capture_output=True, timeout=60, env=env,
            )
            out = r.stdout.decode("utf-8", "replace")
            if '"ok": true' in out or '"ok":true' in out:
                return {"success": True, "provider": "feishu"}
            last = (out or r.stderr.decode("utf-8", "replace"))[:200]
        except Exception as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"feishu send failed: {last}")


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

    max_retries = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
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
        except RuntimeError as exc:
            last_error = exc
            if "iLink" in str(exc) and attempt < max_retries:
                delay = 2 ** attempt  # 2s, 4s, 8s
                print(f"  ⚠️ WeChat iLink error (attempt {attempt}/{max_retries}), retrying in {delay}s...",
                      file=sys.stderr)
                time.sleep(delay)
                continue
            raise
    raise last_error  # type: ignore[misc]


def _send_via_cloud_api(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    base_url = config.get("base_url") or os.getenv("SITE_MONITOR_CLOUD_API_URL")
    token = config.get("upload_token") or os.getenv("SITE_MONITOR_UPLOAD_TOKEN")
    timeout = float(config.get("timeout", 20))

    if not base_url:
        raise ValueError("cloud_api.base_url is required")
    if not token:
        raise ValueError("cloud_api upload token is required")

    url = base_url.rstrip("/") + "/api/v1/reports"
    response = requests.post(
        url,
        json=payload,
        headers={"X-Site-Monitor-Upload-Token": token},
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    result.setdefault("success", True)
    return result


def _save_cloud_sync_failure(
    payload: dict[str, Any],
    config: dict[str, Any],
    error: str,
) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    report_id = payload.get("report_id", "unknown")
    path = Path(runtime_path("pending", f"cloud_sync/{timestamp}-{report_id}.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "payload": payload,
        "config": {
            "base_url": config.get("base_url"),
            "provider": config.get("provider"),
        },
        "error": error,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
