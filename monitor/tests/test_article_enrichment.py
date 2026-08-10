import json

import pytest

from site_monitor import article_enrichment


class FakeModelResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {"message": {"content": json.dumps(self.content, ensure_ascii=False)}}
            ]
        }


def _payload():
    return {
        "report_id": "2026-07-11-test",
        "items": [
            {
                "topic": "openai_news",
                "status": "content",
                "entries": [
                    {
                        "title": "Building reliable agents",
                        "summary": "A practical guide to agent reliability.",
                        "url": "https://example.com/reliable-agents",
                    }
                ],
            },
            {
                "topic": "github_trending",
                "status": "content",
                "entries": [
                    {
                        "title": "owner/project",
                        "url": "https://github.com/owner/project",
                    }
                ],
            },
        ],
    }


def test_feed_entry_excerpt_cleans_html():
    entry = {
        "summary": "<p>A <strong>useful</strong> article.</p>",
        "content": [{"value": "ignored fallback"}],
    }

    assert article_enrichment.feed_entry_excerpt(entry) == "A useful article."


def test_model_summary_is_hard_limited_for_delivery():
    parsed = article_enrichment._parse_model_json(
        json.dumps(
            {
                "items": [
                    {
                        "id": "article:0",
                        "translated_title": "标题",
                        "summary_zh": "长" * 300,
                    }
                ]
            },
            ensure_ascii=False,
        )
    )

    assert len(parsed["article:0"]["summary_zh"]) == 140


def test_enrich_report_adds_translation_summary_and_provenance(monkeypatch):
    prompts = []
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    def fake_fetch(url, timeout, max_chars):
        assert url == "https://example.com/reliable-agents"
        return "The article explains evaluation, retries, and trace-based debugging."

    def fake_post(url, headers, json, timeout):
        prompts.append(json["messages"][0]["content"])
        return FakeModelResponse(
            {
                "items": [
                    {
                        "id": "openai_news:0",
                        "translated_title": "构建可靠的智能体",
                        "summary_zh": "文章介绍如何通过评测、重试和链路追踪提升智能体可靠性。",
                    }
                ]
            }
        )

    result = article_enrichment.enrich_report_payload(
        _payload(),
        {
            "enabled": True,
            "required": True,
            "topics": ["openai_news"],
            "batch_size": 4,
            "retries": 1,
            "model": "test-model",
            "base_url": "https://llm.example.com/v1",
        },
        content_fetcher=fake_fetch,
        http_post=fake_post,
    )

    entry = result["items"][0]["entries"][0]
    assert entry["original_title"] == "Building reliable agents"
    assert entry["translated_title"] == "构建可靠的智能体"
    assert entry["title"] == "构建可靠的智能体"
    assert entry["original_summary"] == "A practical guide to agent reliability."
    assert entry["summary_zh"] == "文章介绍如何通过评测、重试和链路追踪提升智能体可靠性。"
    assert entry["summary"] == entry["summary_zh"]
    assert entry["ai_enrichment"]["model"] == "test-model"
    assert entry["ai_enrichment"]["source_type"] == "article_page"
    assert result["ai_enrichment"]["operations"] == [
        "title_translation",
        "article_summary",
    ]
    assert result["ai_enrichment"]["enriched_count"] == 1
    assert len(prompts) == 1
    assert "translated_title" in prompts[0]
    assert "summary_zh" in prompts[0]
    assert "最多 2 句" in prompts[0]
    assert "不超过 120 个汉字" in prompts[0]
    assert result["items"][1]["entries"][0]["title"] == "owner/project"


def test_no_new_articles_does_not_call_model_or_fetch(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    payload = {
        "items": [
            {
                "topic": "openai_news",
                "status": "no_update",
                "entries": [],
            }
        ]
    }

    result = article_enrichment.enrich_report_payload(
        payload,
        {"enabled": True, "required": True, "topics": ["openai_news"]},
        content_fetcher=lambda *args, **kwargs: pytest.fail("must not fetch"),
        http_post=lambda *args, **kwargs: pytest.fail("must not call model"),
    )

    assert result["ai_enrichment"]["status"] == "no_new_articles"
    assert result["ai_enrichment"]["requested_count"] == 0


def test_required_enrichment_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(article_enrichment, "_load_env", lambda: None)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        article_enrichment.enrich_report_payload(
            _payload(),
            {
                "enabled": True,
                "required": True,
                "topics": ["openai_news"],
            },
            content_fetcher=lambda *args, **kwargs: "article body",
        )
