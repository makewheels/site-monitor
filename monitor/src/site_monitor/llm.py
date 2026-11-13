"""共享 LLM 调用：按 `LLM_PROVIDER_ORDER` 依次尝试多个 provider，失败自动降级到下一个。

设计原则：**默认行为完全不变**。
- 未设置 `LLM_PROVIDER_ORDER`：沿用旧的单一 provider（调用方传入的
  api_key/base_url/model，或环境变量 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`，
  兼容 `DASHSCOPE_API_KEY`）。
- 设置了 `LLM_PROVIDER_ORDER`（如 `baidu,aliyun,deepseek`）：按顺序尝试，谁先
  成功用谁；前一个报错/超时/非 2xx 就自动换下一个。

每个 provider 的配置（都可被环境变量覆盖）：

| name     | key 环境变量(按序取首个非空)                        | base_url 默认                              | model 默认                    |
|----------|-----------------------------------------------------|--------------------------------------------|-------------------------------|
| baidu    | BAIDU_LLM_API_KEY / BAIDU_API_KEY / QIANFAN_API_KEY | https://qianfan.baidubce.com/v2            | deepseek-v4.1-flash-1017      |
| aliyun   | ALIYUN_LLM_API_KEY / DASHSCOPE_API_KEY / LLM_API_KEY| https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen3.7-plus          |
| deepseek | DEEPSEEK_LLM_API_KEY / DEEPSEEK_API_KEY             | https://api.deepseek.com/v1                | deepseek-chat                 |

可分别用 `<NAME>_LLM_BASE_URL` / `<NAME>_LLM_MODEL` 覆盖 base_url / model。
"""
from __future__ import annotations

import os
from typing import Any, Callable

import requests

DEFAULT_ALIYUN_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_ALIYUN_MODEL = "qwen3.7-plus"

_PRESETS: dict[str, dict[str, Any]] = {
    "baidu": {
        "key_envs": ("BAIDU_LLM_API_KEY", "BAIDU_API_KEY", "QIANFAN_API_KEY"),
        "base_url_envs": ("BAIDU_LLM_BASE_URL",),
        "default_base_url": "https://qianfan.baidubce.com/v2",
        "model_envs": ("BAIDU_LLM_MODEL",),
        "default_model": "deepseek-v4.1-flash-1017",
    },
    "aliyun": {
        "key_envs": ("ALIYUN_LLM_API_KEY", "DASHSCOPE_API_KEY", "LLM_API_KEY"),
        "base_url_envs": ("ALIYUN_LLM_BASE_URL", "LLM_BASE_URL"),
        "default_base_url": DEFAULT_ALIYUN_BASE,
        "model_envs": ("ALIYUN_LLM_MODEL", "LLM_MODEL"),
        "default_model": DEFAULT_ALIYUN_MODEL,
    },
    "deepseek": {
        "key_envs": ("DEEPSEEK_LLM_API_KEY", "DEEPSEEK_API_KEY"),
        "base_url_envs": ("DEEPSEEK_LLM_BASE_URL",),
        "default_base_url": "https://api.deepseek.com/v1",
        "model_envs": ("DEEPSEEK_LLM_MODEL",),
        "default_model": "deepseek-chat",
    },
}


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def providers() -> list[dict[str, str]]:
    """返回当前可用的 provider 列表（已按优先级排序，缺密钥的会被跳过）。"""
    order = os.environ.get("LLM_PROVIDER_ORDER", "").strip()
    if not order:
        key = os.environ.get("LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
        if not key:
            return []
        return [
            {
                "name": "default",
                "api_key": key,
                "base_url": os.environ.get("LLM_BASE_URL") or DEFAULT_ALIYUN_BASE,
                "model": os.environ.get("LLM_MODEL") or DEFAULT_ALIYUN_MODEL,
            }
        ]

    result: list[dict[str, str]] = []
    for name in [item.strip() for item in order.split(",") if item.strip()]:
        preset = _PRESETS.get(name)
        if not preset:
            continue
        key = _first_env(preset["key_envs"])
        if not key:
            continue
        result.append(
            {
                "name": name,
                "api_key": key,
                "base_url": _first_env(preset["base_url_envs"]) or preset["default_base_url"],
                "model": _first_env(preset["model_envs"]) or preset["default_model"],
            }
        )
    return result


def has_provider() -> bool:
    return bool(providers())


def chat(
    messages: list[dict[str, Any]],
    *,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    timeout: float = 90,
    response_format: dict[str, Any] | None = None,
    http_post: Callable[..., Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """调用 `/chat/completions`，返回解析后的 JSON。

    - 设置了 `LLM_PROVIDER_ORDER`：忽略传入的单一 provider 参数，按顺序降级。
    - 否则：沿用传入的 api_key/base_url/model（或环境变量单 provider）。
    """
    order = os.environ.get("LLM_PROVIDER_ORDER", "").strip()
    if order:
        chain = providers()
        if not chain:
            raise RuntimeError("LLM_PROVIDER_ORDER 已设置，但对应 provider 的密钥都缺失")
    elif api_key and base_url:
        chain = [
            {
                "name": "explicit",
                "api_key": api_key,
                "base_url": base_url,
                "model": model or DEFAULT_ALIYUN_MODEL,
            }
        ]
    else:
        chain = providers()
        if not chain:
            raise RuntimeError("未配置任何 LLM provider（LLM_API_KEY / LLM_PROVIDER_ORDER）")

    post = http_post or requests.post
    last_error: Exception | None = None
    for provider in chain:
        body: dict[str, Any] = {"model": provider["model"], "messages": messages}
        if response_format is not None:
            body["response_format"] = response_format
        body.update(extra)
        try:
            response = post(
                provider["base_url"].rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {provider['api_key']}"},
                json=body,
                timeout=timeout,
            )
            status = getattr(response, "status_code", None)
            if status is not None and status >= 400:
                raise RuntimeError(f"HTTP {status}: {str(getattr(response, 'text', ''))[:200]}")
            raise_for_status = getattr(response, "raise_for_status", None)
            if raise_for_status is not None:
                raise_for_status()
            data = response.json()
            print(f"[llm] 使用 {provider['name']} ({provider['model']})")
            return data
        except Exception as exc:  # noqa: BLE001 - 逐个降级，最后一个错误抛出
            last_error = exc
            print(f"[llm] {provider['name']} 失败，降级: {exc}")
    raise RuntimeError(f"所有 LLM provider 均失败: {last_error}") from last_error