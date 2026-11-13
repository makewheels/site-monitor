import json

from site_monitor import llm


class FakeResp:
    def __init__(self, payload, status=200, raise_exc=None):
        self._payload = payload
        self.status_code = status
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


def test_provider_order_falls_back_when_primary_fails(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "baidu,aliyun")
    monkeypatch.setenv("BAIDU_LLM_API_KEY", "b-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "a-key")
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, json["model"]))
        if "qianfan" in url:
            raise RuntimeError("baidu down")
        return FakeResp({"choices": [{"message": {"content": "{}"}}]})

    data = llm.chat([{"role": "user", "content": "hi"}], http_post=fake_post)

    assert data["choices"][0]["message"]["content"] == "{}"
    assert len(calls) == 2
    assert "qianfan" in calls[0][0]
    assert "dashscope" in calls[1][0]


def test_no_order_keeps_legacy_single_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER_ORDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "legacy")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    provs = llm.providers()

    assert len(provs) == 1
    assert provs[0]["name"] == "default"


def test_order_skips_providers_without_keys(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "baidu,deepseek,aliyun")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "a-key")
    for name in ("BAIDU_LLM_API_KEY", "BAIDU_API_KEY", "QIANFAN_API_KEY",
                 "DEEPSEEK_LLM_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    names = [p["name"] for p in llm.providers()]

    assert names == ["aliyun"]


def test_all_providers_failing_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "aliyun")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "a-key")

    def fake_post(url, headers, json, timeout):
        return FakeResp({}, status=500)

    try:
        llm.chat([{"role": "user", "content": "hi"}], http_post=fake_post)
        assert False, "should raise"
    except RuntimeError as exc:
        assert "所有 LLM provider 均失败" in str(exc)