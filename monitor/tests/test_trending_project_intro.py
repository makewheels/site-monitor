from site_monitor.postprocessors import trending_project_intro
from site_monitor.postprocess import get_postprocessor_specs


def test_project_deck_generation_is_disabled_in_production_config():
    specs = get_postprocessor_specs("github_trending")
    project_deck = next(
        spec
        for spec in specs
        if spec.get("module", "").endswith("trending_project_intro")
    )

    assert project_deck["enabled"] is False


def test_enrich_generates_and_reuses_cached_project_intro(monkeypatch, tmp_path):
    calls = []
    metadata = {
        "full_name": "owner/project",
        "description": "A useful tool",
        "homepage": "",
        "language": "Python",
        "license": "MIT",
        "stars": 123,
        "forks": 12,
        "open_issues": 3,
        "topics": [],
        "created_at": "2026-01-01T00:00:00Z",
        "pushed_at": "2026-08-09T00:00:00Z",
        "default_branch": "main",
        "repository_url": "https://github.com/owner/project",
    }

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(
        trending_project_intro,
        "CACHE_FILE",
        str(tmp_path / "project-intros.json"),
    )
    monkeypatch.setattr(
        trending_project_intro,
        "_fetch_metadata",
        lambda full_name, timeout: dict(metadata),
    )
    monkeypatch.setattr(
        trending_project_intro,
        "_fetch_readme",
        lambda full_name, timeout, limit: "# Project\nA useful README",
    )

    def generate(*args, **kwargs):
        calls.append(kwargs["model"])
        return {
            "title": "Project 项目解读",
            "tagline": "一句话定位",
            "problem": "解决复杂任务的问题",
            "architecture": [{"name": "Core", "description": "处理任务"}],
            "audience": ["平台工程师"],
            "workflow": [{"name": "输入", "description": "接收任务"}],
            "core_concepts": [{"name": "队列", "description": "调度任务"}],
            "alternatives": [
                {"name": "简单脚本", "when_choose": "一次性任务", "tradeoff": "缺少治理"}
            ],
            "questions": ["能否自托管？"],
            "why_choose": ["需要自动化"],
            "avoid_when": ["只需要简单脚本"],
            "use_cases": ["批量处理"],
            "getting_started": ["阅读 README"],
            "risks": ["需要审查输出"],
            "source_urls": [],
        }

    monkeypatch.setattr(trending_project_intro, "_request_intro", generate)
    options = {"page_base_url": "https://monitor.example.com/projects", "workers": 1}

    first = trending_project_intro.enrich(
        {"repos": [{"full_name": "owner/project", "description": "A useful tool"}]},
        options,
    )
    second = trending_project_intro.enrich(first, options)

    repo = second["repos"][0]
    assert calls == ["test-model"]
    assert repo["intro_url"] == "https://monitor.example.com/projects/owner/project"
    assert repo["source_url"] == "https://github.com/owner/project"
    assert repo["project_intro"]["architecture"] == [
        {"name": "Core", "description": "处理任务"}
    ]
    assert repo["project_intro"]["facts"]["stars"] == 123
    assert repo["project_intro"]["schema_version"] == 2
    assert repo["project_intro"]["workflow"][0]["name"] == "输入"
    assert repo["project_intro"]["model"] == "test-model"
