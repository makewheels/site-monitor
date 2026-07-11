import pytest

from site_monitor import daily_summary


def test_article_enrichment_failure_rolls_back_monitor_state(monkeypatch, tmp_path):
    def fake_runtime_dir(kind):
        path = tmp_path / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fake_runtime_path(kind, filename):
        path = fake_runtime_dir(kind) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    state_file = fake_runtime_dir("state") / "openai_news_state.json"
    state_file.write_text('{"known_urls": ["old"]}')

    def fake_run_script(module_name):
        state_file.write_text('{"known_urls": ["new"]}')
        return ""

    monkeypatch.setattr(daily_summary, "runtime_dir", fake_runtime_dir)
    monkeypatch.setattr(daily_summary, "runtime_path", fake_runtime_path)
    monkeypatch.setattr(daily_summary, "run_script", fake_run_script)
    monkeypatch.setattr(
        daily_summary,
        "enrich_report_payload",
        lambda payload: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        daily_summary.build_report_payload()

    assert state_file.read_text() == '{"known_urls": ["old"]}'
