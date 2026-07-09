import json

from site_monitor.postprocessors import trending_summary


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def test_summarize_adds_zh_summary(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResp({"choices": [{"message": {"content": json.dumps({
            "owner/repo1": "中文总结1", "owner/repo2": "中文总结2",
        })}}]})

    monkeypatch.setattr(trending_summary, "_load_env", lambda: None)
    monkeypatch.setattr(trending_summary.requests, "post", fake_post)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

    result = trending_summary.summarize(
        {"repos": [
            {"full_name": "owner/repo1", "description": "desc1"},
            {"full_name": "owner/repo2", "description": "desc2"},
        ]},
        {},
    )

    assert result["repos"][0]["zh_summary"] == "中文总结1"
    assert result["repos"][1]["zh_summary"] == "中文总结2"


def test_summarize_fallback_on_llm_failure(monkeypatch):
    def fake_post(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(trending_summary, "_load_env", lambda: None)
    monkeypatch.setattr(trending_summary.requests, "post", fake_post)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

    result = trending_summary.summarize(
        {"repos": [{"full_name": "o/r", "description": "d"}]}, {}
    )

    # LLM 失败 -> 原样返回,无 zh_summary(check_github_trending 回退词典)
    assert "zh_summary" not in result["repos"][0]


def test_summarize_skips_without_key(monkeypatch):
    monkeypatch.setattr(trending_summary, "_load_env", lambda: None)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    result = trending_summary.summarize(
        {"repos": [{"full_name": "o/r", "description": "d"}]}, {}
    )

    assert "zh_summary" not in result["repos"][0]
