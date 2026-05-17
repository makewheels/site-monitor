# Agent Workflow

This repository backs the local daily AI monitor that Hermes sends each morning.

## Monitor Sources

- Keep external feed, RSSHub, Atom, API, and raw changelog URLs in `config.json` under `monitor_sources`.
- Read those values through `monitor_config.get_monitor_source()` instead of hardcoding URLs inside individual monitor scripts.
- Keep implementation code under `src/site_monitor/`.
- Root-level `daily_summary.py`, `main.py`, and `notifier.py` are compatibility wrappers only. Manual `check_*.py` wrappers live under `scripts/`.
- Prefer RSS/Atom sources when available. Keep a direct page/API fallback when public RSSHub instances can fail.
- Public RSSHub instances are acceptable for now, but order them with `https://rsshub.app/...` first and a working public fallback second.
- Do not write API keys, cookies, or private tokens into `config.json`.

## Runtime Files

- Runtime output belongs under `runtime/`, not the repository root.
- Use `monitor_config.runtime_path(kind, filename)` for state, pending, logs, and temporary files.
- Current runtime directories:
  - `runtime/state/` for durable local state such as seen article IDs.
  - `runtime/pending/` for files consumed by `daily_summary.py`.
  - `runtime/logs/` for local logs.
  - `runtime/tmp/` for scratch files.
- Do not commit runtime contents; only `.gitkeep` placeholders are tracked.

## Tests

- Add or update tests under `tests/` for monitor parsing and filtering logic.
- Tests should be offline: mock network calls and feed parsers instead of calling GitHub, RSSHub, or vendor pages.
- Before committing, run:

```bash
python3 -m json.tool config.json >/dev/null
python3 -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
python3 -m pytest
```

## Daily Report Behavior

- Monitor scripts write their user-facing output to `*_pending.txt`.
- `daily_summary.py` runs the individual monitor scripts and prints non-empty pending files for Hermes delivery.
- For Claude Code, keep filtering noisy patch-only bugfixes unless the change is security, permissions, data loss, breaking behavior, or a major/minor version change.
