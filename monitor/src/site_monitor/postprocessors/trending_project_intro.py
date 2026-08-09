"""Generate reusable, evidence-based project briefs for GitHub Trending."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

import requests

from . import _load_env
from ..monitor_config import runtime_path


CACHE_FILE = runtime_path("state", "github_project_intros_state.json")
INTRO_SCHEMA_VERSION = 2
DEFAULT_PAGE_BASE_URL = "https://site-monitor.a4.fit/projects"
FULL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _read_cache() -> dict[str, Any]:
    path = Path(CACHE_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"projects": {}}
    return data if isinstance(data, dict) else {"projects": {}}


def _write_cache(data: dict[str, Any]) -> None:
    path = Path(CACHE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _github_headers(*, raw: bool = False) -> dict[str, str]:
    headers = {
        "Accept": (
            "application/vnd.github.raw+json"
            if raw
            else "application/vnd.github+json"
        ),
        "User-Agent": "site-monitor-project-briefs",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_metadata(full_name: str, *, timeout: float) -> dict[str, Any]:
    response = requests.get(
        f"https://api.github.com/repos/{full_name}",
        headers=_github_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    language_distribution: list[dict[str, Any]] = []
    try:
        languages_response = requests.get(
            f"https://api.github.com/repos/{full_name}/languages",
            headers=_github_headers(),
            timeout=timeout,
        )
        languages_response.raise_for_status()
        language_bytes = languages_response.json()
        total_bytes = sum(
            int(value)
            for value in language_bytes.values()
            if isinstance(value, (int, float)) and value > 0
        )
        if total_bytes:
            language_distribution = [
                {
                    "name": str(name)[:80],
                    "percent": round(int(value) * 100 / total_bytes, 1),
                }
                for name, value in sorted(
                    language_bytes.items(), key=lambda item: item[1], reverse=True
                )[:5]
                if isinstance(value, (int, float)) and value > 0
            ]
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    license_data = data.get("license") or {}
    return {
        "full_name": full_name,
        "description": data.get("description") or "",
        "homepage": data.get("homepage") or "",
        "language": data.get("language") or "未标注",
        "license": license_data.get("spdx_id") or "未标注",
        "stars": int(data.get("stargazers_count") or 0),
        "forks": int(data.get("forks_count") or 0),
        "open_issues": int(data.get("open_issues_count") or 0),
        "topics": data.get("topics") or [],
        "language_distribution": language_distribution,
        "created_at": data.get("created_at") or "",
        "pushed_at": data.get("pushed_at") or "",
        "default_branch": data.get("default_branch") or "main",
        "repository_url": data.get("html_url") or f"https://github.com/{full_name}",
    }


def _fetch_readme(full_name: str, *, timeout: float, limit: int) -> str:
    response = requests.get(
        f"https://api.github.com/repos/{full_name}/readme",
        headers=_github_headers(raw=True),
        timeout=timeout,
    )
    if response.status_code == 404:
        return ""
    response.raise_for_status()
    return response.text[:limit]


def _extract_json(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("project intro response must be a JSON object")
    return data


def _string_list(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:500] for item in value if str(item).strip()][:limit]


def _named_cards(value: Any, *, limit: int = 6) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:limit]:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()[:100]
            description = str(item.get("description") or "").strip()[:600]
        else:
            name = "核心组件"
            description = str(item).strip()[:600]
        if name and description:
            result.append({"name": name, "description": description})
    return result


def _alternatives(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:100]
        when_choose = str(item.get("when_choose") or "").strip()[:400]
        tradeoff = str(item.get("tradeoff") or "").strip()[:400]
        if name and (when_choose or tradeoff):
            result.append(
                {"name": name, "when_choose": when_choose, "tradeoff": tradeoff}
            )
    return result


def _normalise_intro(data: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    full_name = metadata["full_name"]
    repository_url = metadata["repository_url"]
    return {
        "schema_version": INTRO_SCHEMA_VERSION,
        "full_name": full_name,
        "title": str(data.get("title") or full_name).strip()[:180],
        "tagline": str(data.get("tagline") or metadata.get("description") or "").strip()[:500],
        "problem": str(data.get("problem") or "").strip()[:1_200],
        "audience": _string_list(data.get("audience"), limit=4),
        "workflow": _named_cards(data.get("workflow"), limit=5),
        "core_concepts": _named_cards(data.get("core_concepts"), limit=6),
        "architecture": _named_cards(data.get("architecture"), limit=6),
        "why_choose": _string_list(data.get("why_choose")),
        "avoid_when": _string_list(data.get("avoid_when")),
        "use_cases": _string_list(data.get("use_cases")),
        "getting_started": _string_list(data.get("getting_started")),
        "risks": _string_list(data.get("risks")),
        "alternatives": _alternatives(data.get("alternatives")),
        "questions": _string_list(data.get("questions"), limit=5),
        "facts": {
            "language": metadata.get("language"),
            "license": metadata.get("license"),
            "stars": metadata.get("stars"),
            "forks": metadata.get("forks"),
            "open_issues": metadata.get("open_issues"),
            "created_at": metadata.get("created_at"),
            "pushed_at": metadata.get("pushed_at"),
            "topics": _string_list(metadata.get("topics"), limit=8),
            "language_distribution": metadata.get("language_distribution") or [],
        },
        "source_urls": list(
            dict.fromkeys(
                [
                    repository_url,
                    f"{repository_url}/blob/{metadata.get('default_branch')}/README.md",
                ]
            )
        ),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _fallback_intro(repo: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    description = repo.get("zh_summary") or metadata.get("description") or repo.get("description") or ""
    return _normalise_intro(
        {
            "title": metadata["full_name"],
            "tagline": description,
            "problem": "模型暂未完成深度解读，请先根据项目简介和源代码判断用途。",
            "architecture": [],
            "audience": ["第一次评估这个开源项目的开发者或技术负责人"],
            "workflow": [],
            "core_concepts": [],
            "why_choose": [],
            "avoid_when": ["需要完整技术评估时，不要只依赖当前简版介绍"],
            "use_cases": [],
            "getting_started": ["先阅读 README，再在隔离环境中试用"],
            "risks": ["当前页面仅包含公开仓库元数据，架构细节尚未由模型确认"],
            "alternatives": [],
            "questions": ["README 是否覆盖你的实际部署环境？", "许可证是否符合使用场景？"],
        },
        metadata,
    )


def _request_intro(
    metadata: dict[str, Any],
    readme: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> dict[str, Any]:
    prompt = (
        "你是资深软件架构师和技术编辑。只根据给定 GitHub 元数据与 README，"
        "为第一次看到该项目的中文读者写一份可核验的项目解读。重点讲清它解决什么问题、"
        "核心架构/工作原理、为什么选择、何时不要选择、真实场景、上手步骤与风险。"
        "还要帮助读者在 3 分钟内完成是否值得继续研究的判断：目标用户、端到端工作流、"
        "核心概念、同类方案取舍，以及评估前应该追问的问题。每条描述要具体、简洁并基于证据。"
        "不要写营销套话，不确定就明确说未确认。严格返回 JSON 对象，字段为："
        "title(string), tagline(string), problem(string), audience([string]), "
        "workflow([{name,description}]), core_concepts([{name,description}]), "
        "architecture([{name,description}]), alternatives([{name,when_choose,tradeoff}]), "
        "questions([string]), why_choose([string]), "
        "avoid_when([string]), use_cases([string]), getting_started([string]), "
        "risks([string])。\n\n"
        f"项目元数据：\n{json.dumps(metadata, ensure_ascii=False)}\n\n"
        f"README：\n{readme or 'README 暂不可获取'}"
    )
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


def enrich(payload: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    repos = payload.get("repos") or []
    if not repos:
        return payload

    _load_env()
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or ""
    base_url = str(
        options.get("base_url")
        or os.environ.get("LLM_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = str(options.get("model") or os.environ.get("LLM_MODEL") or "qwen3.7-plus")
    page_base_url = str(
        options.get("page_base_url")
        or os.environ.get("SITE_MONITOR_PROJECT_PAGE_BASE_URL")
        or DEFAULT_PAGE_BASE_URL
    ).rstrip("/")
    fetch_timeout = float(options.get("fetch_timeout", 20))
    request_timeout = float(options.get("request_timeout", 120))
    max_readme_chars = int(options.get("max_readme_chars", 8_000))
    workers = max(1, min(int(options.get("workers", 2)), 4))
    cache = _read_cache()
    cached_projects = cache.get("projects") if isinstance(cache.get("projects"), dict) else {}

    def process(repo: dict[str, Any]) -> dict[str, Any]:
        result = dict(repo)
        full_name = str(result.get("full_name") or "")
        if not FULL_NAME_PATTERN.fullmatch(full_name):
            return result
        cached = cached_projects.get(full_name.lower()) or {}
        try:
            metadata = _fetch_metadata(full_name, timeout=fetch_timeout)
        except Exception as exc:
            if cached.get("intro"):
                result["project_intro"] = cached["intro"]
            result["project_intro_error"] = f"metadata: {exc}"
            return result

        intro = None
        if (
            cached.get("schema_version") == INTRO_SCHEMA_VERSION
            and cached.get("pushed_at") == metadata.get("pushed_at")
            and cached.get("intro")
        ):
            intro = _normalise_intro(cached["intro"], metadata)
        elif api_key:
            try:
                readme = _fetch_readme(
                    full_name,
                    timeout=fetch_timeout,
                    limit=max_readme_chars,
                )
                generated = _request_intro(
                    metadata,
                    readme,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    timeout=request_timeout,
                )
                intro = _normalise_intro(generated, metadata)
            except Exception as exc:
                result["project_intro_error"] = f"generation: {exc}"
        if intro is None:
            intro = _fallback_intro(result, metadata)

        intro["model"] = model if api_key else "fallback"
        result["project_intro"] = intro
        result["intro_url"] = f"{page_base_url}/{full_name}"
        result["source_url"] = metadata["repository_url"]
        return result

    with ThreadPoolExecutor(max_workers=min(workers, len(repos))) as executor:
        processed_repos = list(executor.map(process, repos))

    updated_cache = dict(cached_projects)
    for repo in processed_repos:
        intro = repo.get("project_intro")
        full_name = str(repo.get("full_name") or "")
        if not intro or not full_name:
            continue
        updated_cache[full_name.lower()] = {
            "schema_version": INTRO_SCHEMA_VERSION,
            "pushed_at": intro.get("facts", {}).get("pushed_at"),
            "intro": intro,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    if len(updated_cache) > 200:
        updated_cache = dict(
            sorted(
                updated_cache.items(),
                key=lambda item: item[1].get("updated_at", ""),
                reverse=True,
            )[:200]
        )
    _write_cache({"projects": updated_cache})
    return {**payload, "repos": processed_repos}
