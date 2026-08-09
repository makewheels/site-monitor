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
        return _send_via_feishu(message, config, payload)
    if provider == "cloud_api":
        return _send_via_cloud_api(payload, config)
    raise ValueError(f"Unsupported delivery provider: {provider}")


def _send_via_feishu(
    message: str,
    config: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Send a report to Feishu using Open API or the local lark-cli fallback."""
    _load_env_file(PROJECT_ROOT / ".env")
    app_id = config.get("app_id") or os.getenv("FEISHU_APP_ID", "")
    app_secret = config.get("app_secret") or os.getenv("FEISHU_APP_SECRET", "")
    if app_id and app_secret:
        return _send_via_feishu_api(message, config, app_id, app_secret, payload)

    return _send_via_feishu_cli(message, config)


def _send_via_feishu_api(
    message: str,
    config: dict[str, Any],
    app_id: str,
    app_secret: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    base_url = (config.get("base_url") or os.getenv("FEISHU_BASE_URL") or "https://open.feishu.cn").rstrip("/")
    user_id = config.get("user_id") or os.getenv("FEISHU_USER_ID", "")
    chat_id = config.get("chat_id") or os.getenv("FEISHU_CHAT_ID", "")
    if user_id:
        receive_id_type = "open_id"
        receive_id = user_id
    elif chat_id:
        receive_id_type = "chat_id"
        receive_id = chat_id
    else:
        raise ValueError("FEISHU_USER_ID or FEISHU_CHAT_ID is required")

    token_result = _feishu_post_json(
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        json_body={"app_id": app_id, "app_secret": app_secret},
        timeout=30,
    )
    access_token = token_result.get("tenant_access_token")
    if not access_token:
        raise RuntimeError("Feishu token response did not include tenant_access_token")

    markdown = config.get("markdown", True)
    max_chars = int(config.get("max_chars", 12_000))
    if markdown and payload.get("items"):
        messages = [
            ("interactive", json.dumps(card, ensure_ascii=False))
            for card in _build_feishu_cards(payload, max_chars)
        ]
    else:
        chunks = _split_message(message, max_chars)
        messages = []
        for index, chunk in enumerate(chunks, 1):
            if markdown:
                title = "每日 AI 监控"
                if len(chunks) > 1:
                    title += f" ({index}/{len(chunks)})"
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "blue",
                        "title": {"tag": "plain_text", "content": title},
                    },
                    "elements": [{"tag": "markdown", "content": chunk}],
                }
                messages.append(("interactive", json.dumps(card, ensure_ascii=False)))
            else:
                messages.append(("text", json.dumps({"text": chunk}, ensure_ascii=False)))

    for msg_type, content in messages:

        _feishu_post_json(
            f"{base_url}/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {access_token}"},
            json_body={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content,
            },
            timeout=30,
        )

    return {"success": True, "provider": "feishu", "message_count": len(messages)}


_TOPIC_ICONS = {
    "github_trending": "🔥",
    "anthropic_engineering": "A",
    "openai_news": "O",
    "langchain_blog": "L",
    "claude_code": "C",
    "github_copilot_cli": "⌘",
    "huggingface_blog": "HF",
    "google_research": "G",
    "metr": "M",
    "swe_bench": "SWE",
    "trail_of_bits": "ToB",
    "owasp_llm_top10": "OWASP",
}


def _topic_markdown(item: dict[str, Any], *, show_heading: bool = True) -> str:
    entries = item.get("entries") or []
    lines: list[str] = []
    if show_heading:
        icon = _TOPIC_ICONS.get(item.get("topic", ""), "AI")
        count = f" · {len(entries)} 条" if entries else ""
        lines.append(f"**{icon}  {item.get('topic_name', item.get('title', '更新'))}{count}**")
    for index, entry in enumerate(entries, 1):
        if lines:
            lines.append("")
        title = entry.get("translated_title") or entry.get("title", "未命名")
        intro_url = entry.get("intro_url")
        source_url = entry.get("source_url")
        if intro_url:
            lines.append(f"**{index}. [{title}]({intro_url})**")
        else:
            lines.append(f"**{index}. {title}**")
        original_title = entry.get("original_title")
        if original_title and original_title != title:
            lines.append(f"原题：{original_title}")
        if entry.get("summary"):
            prefix = "AI 摘要：" if entry.get("summary_zh") else ""
            lines.append(prefix + str(entry["summary"]))
        if entry.get("meta"):
            lines.append(f"{entry['meta']}")
        if intro_url:
            links = [f"📖 [手机项目解读]({intro_url})"]
            if source_url:
                links.append(f"💻 [GitHub 源码]({source_url})")
            lines.append(" · ".join(links))
        elif entry.get("url"):
            lines.append(f"🔗 {entry['url']}")
    if not entries:
        body_lines = [
            line
            for line in str(item.get("body", "")).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        lines.extend(body_lines)
    return "\n".join(lines).strip()


def _build_feishu_cards(payload: dict[str, Any], max_chars: int) -> list[dict[str, Any]]:
    items = payload.get("items") or []
    active = [item for item in items if item.get("status") != "no_update"]
    inactive = [item.get("topic_name", item.get("title", "")) for item in items if item.get("status") == "no_update"]
    if not active:
        active = items[:1]

    blocks: list[tuple[dict[str, Any], str]] = []
    for item in active:
        blocks.append(
            (
                item,
                _topic_markdown(
                    item,
                    show_heading=item.get("topic") != "github_trending",
                ),
            )
        )

    groups: list[list[tuple[dict[str, Any], str]]] = []
    current: list[tuple[dict[str, Any], str]] = []
    current_size = 0
    for item, block in blocks:
        if current and current_size + len(block) > max_chars:
            groups.append(current)
            current = []
            current_size = 0
        current.append((item, block))
        current_size += len(block)
    if current:
        groups.append(current)

    cards: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups, 1):
        first_item = group[0][0]
        entries = first_item.get("entries") or []
        if group_index == 1 and str(first_item.get("topic", "")).startswith("github_trending"):
            period = "本周" if first_item.get("topic") == "github_trending_weekly" else "今日"
            title = f"🔥 {period} GitHub Trending · {len(entries)} 个项目"
            template = "green"
        else:
            title = f"AI 早报 · {payload.get('date', '')}"
            template = "blue"
        if len(groups) > 1:
            title += f" ({group_index}/{len(groups)})"

        elements: list[dict[str, Any]] = [
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"AI 早报 · {payload.get('date', '')}",
                    }
                ],
            }
        ]
        for block_index, (_, block) in enumerate(group):
            if block_index:
                elements.append({"tag": "hr"})
            elements.append({"tag": "markdown", "content": block})
        if group_index == len(groups) and inactive:
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "今日无更新：" + "、".join(inactive),
                        }
                    ],
                }
            )
        cards.append(
            {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": template,
                    "title": {"tag": "plain_text", "content": title},
                },
                "elements": elements,
            }
        )
    return cards


def _feishu_post_json(
    url: str,
    *,
    json_body: dict[str, Any],
    timeout: float,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                params=params,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code", 0) != 0:
                raise RuntimeError(
                    f"Feishu API error {result.get('code')}: {result.get('msg', 'unknown error')}"
                )
            return result
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Feishu API request failed: {last_error}") from last_error


def _split_message(message: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if len(message) <= max_chars:
        return [message]

    chunks: list[str] = []
    current = ""
    for paragraph in message.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_chars:
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _send_via_feishu_cli(message: str, config: dict[str, Any]) -> dict[str, Any]:
    """Use the workstation lark-cli when Open API credentials are unavailable."""
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
        raise ValueError("FEISHU_USER_ID 或 FEISHU_CHAT_ID 未配置(写 monitor/.env)")

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
