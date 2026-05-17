# Agent Workflow

This repository backs the local daily AI monitor that Hermes sends each morning.

## Monitor Sources

- Keep external feed, RSSHub, Atom, API, and raw changelog URLs in `config.json` under `monitor_sources`.
- Read those values through `monitor_config.get_monitor_source()` instead of hardcoding URLs inside individual monitor scripts.
- Prefer RSS/Atom sources when available. Keep a direct page/API fallback when public RSSHub instances can fail.
- Public RSSHub instances are acceptable for now, but order them with `https://rsshub.app/...` first and a working public fallback second.
- Do not write API keys, cookies, or private tokens into `config.json`.

## Tests

- Add or update tests under `tests/` for monitor parsing and filtering logic.
- Tests should be offline: mock network calls and feed parsers instead of calling GitHub, RSSHub, or vendor pages.
- Before committing, run:

```bash
python3 -m json.tool config.json >/dev/null
python3 -m py_compile monitor_config.py check_anthropic.py check_claude_code.py check_copilot_cli.py daily_summary.py
python3 -m pytest
```

## Daily Report Behavior

- Monitor scripts write their user-facing output to `*_pending.txt`.
- `daily_summary.py` runs the individual monitor scripts and prints non-empty pending files for Hermes delivery.
- For Claude Code, keep filtering noisy patch-only bugfixes unless the change is security, permissions, data loss, breaking behavior, or a major/minor version change.
