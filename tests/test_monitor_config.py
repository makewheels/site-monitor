import json
from site_monitor import monitor_config


def test_get_monitor_source_reads_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "monitor_sources": {
                    "example": {
                        "atom_url": "https://example.com/feed.atom",
                    }
                }
            }
        )
    )
    monkeypatch.setattr(monitor_config, "CONFIG_FILE", config_file)

    assert monitor_config.get_monitor_source("example") == {
        "atom_url": "https://example.com/feed.atom",
    }
    assert monitor_config.get_monitor_source("missing") == {}
