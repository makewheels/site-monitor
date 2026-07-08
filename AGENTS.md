# Agent Workflow

This repository backs the local AI monitor. Run `daily_summary.py` manually when you want a report; there is no scheduler. Delivery is disabled—output goes to the terminal.

## Monitor Sources

- Keep external feed, RSSHub, Atom, API, and raw changelog URLs in `config.json` under `monitor_sources`.
- Read those values through `monitor_config.get_monitor_source()` instead of hardcoding URLs inside individual monitor scripts.
- Keep implementation code under `src/site_monitor/`.
- Root-level `daily_summary.py`, `main.py`, and `notifier.py` are compatibility wrappers only. Manual `check_*.py` wrappers live under `scripts/`.
- Prefer RSS/Atom sources when available. Keep a direct page/API fallback when public RSSHub instances can fail.
- Config-driven RSS/Atom feeds live under `config.json` `rss_feeds` (list of `{key, name, urls, limit}`), read via `monitor_config.get_rss_feeds()` and run by `check_rss_feeds`. Add a new RSS source by appending to `rss_feeds` plus a `Topic` in `report_payload.TOPICS`-no new module needed.
- Public RSSHub instances are acceptable for now, but order them with `https://rsshub.app/...` first and a working public fallback second.
- Do not write API keys, cookies, or private tokens into `config.json`.
- Claude Code should use only the RSSHub changelog route unless the user asks to add another source.

## Postprocessors

- Keep configurable postprocessing under `config.json` in `postprocessors`.
- A postprocessor is a Python function addressed by `module` and `function`; it receives a payload dict plus `options` and returns a payload dict.
- Use postprocessors for filtering, section splitting, translation, or future AI cleanup instead of embedding that behavior directly in feed fetchers.
- For changelogs, split important feature changes from fix/docs/chore items so the daily report is scannable.

## Delivery

- Delivery is owned by this project through `src/site_monitor/delivery.py`, controlled by `config.json` `delivery.enabled`.
- Currently `delivery.enabled` is `false`: `daily_summary.py` prints the report to the terminal only. Re-enable by setting `enabled: true` (backend `hermes_weixin` reuses local Hermes Weixin credentials from `~/.hermes/.env`).
- There is no longer a Hermes cron schedule or fallback delivery; run `daily_summary.py` manually.

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
- `daily_summary.py` runs the individual monitor scripts, prints non-empty pending files, and prints the assembled report to the terminal (sends via configured delivery only if `delivery.enabled` is true).
- For Claude Code, keep the changelog visible but separate feature changes from fix/docs/chore items through the configured postprocessor.
