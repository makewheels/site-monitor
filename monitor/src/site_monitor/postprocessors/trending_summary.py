"""LLM 中文总结 postprocessor for github_trending.

接收 payload {"repos": [{"full_name", "description", ...}]},批量调 DashScope
给每个 repo 生成一句中文总结,写回 r["zh_summary"]。LLM 失败则原样返回,
由 check_github_trending 回退到词典翻译。
"""
import json
import os
from pathlib import Path

import requests

from . import _load_env  # type: ignore


def summarize(payload: dict, options: dict) -> dict:
    repos = payload.get("repos", [])
    if not repos:
        return payload

    _load_env()
    key = os.environ.get("DASHSCOPE_API_KEY")
    base_url = options.get("base_url") or os.environ.get(
        "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = options.get("model") or os.environ.get("LLM_MODEL", "qwen3.7-plus")
    if not key:
        print("trending 中文总结跳过: 未配置 DASHSCOPE_API_KEY")
        return payload

    items = [
        {"name": r.get("full_name", ""), "desc": r.get("description", "")}
        for r in repos
    ]
    prompt = (
        "你是资深技术编辑。给每个 GitHub 项目写一句简炼中文总结(它做什么/亮点),"
        "口语化、全中文(专有名词/项目名除外)、不要重复项目名、≤30字。"
        "严格只返回 JSON: {\"项目名\":\"中文总结\"}。\n\n项目列表:\n"
        + json.dumps(items, ensure_ascii=False)
    )

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        summaries = json.loads(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"trending 中文总结失败,回退词典翻译: {e}")
        return payload

    for r in repos:
        r["zh_summary"] = summaries.get(r.get("full_name", ""), "")
    return payload
