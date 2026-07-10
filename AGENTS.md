# Agent Workflow

This repository backs the daily AI monitor. GitHub Actions runs the full monitor at 07:00 Asia/Shanghai, persists monitor state and reports to MongoDB, and delivers the digest to Feishu.

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
- The production backend is `feishu`. CI uses `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and one of `FEISHU_USER_ID` / `FEISHU_CHAT_ID` from GitHub variables and secrets.
- The workstation-only `lark-cli` path remains a fallback when Open API credentials are absent.
- Never put Feishu credentials, MongoDB URIs, server addresses, or API keys in tracked files.

## Schedule

- `.github/workflows/daily-monitor.yml` is the only production scheduler.
- Keep the schedule timezone explicit as `Asia/Shanghai`; all feeds are collected once per day for the 07:00 digest.
- Monitor state is restored from and saved to the MongoDB `monitor_state` collection so ephemeral CI runners do not resend old entries.

## Runtime Files

- Runtime output belongs under `runtime/`, not the repository root.
- Use `monitor_config.runtime_path(kind, filename)` for state, pending, logs, and temporary files.
- Set `SITE_MONITOR_RUNTIME_DIR` to move runtime files to a persistent external directory.
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
uv run python -m json.tool config.json >/dev/null
uv run python -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
uv run pytest
```

## Daily Report Behavior

- Monitor scripts write their user-facing output to `*_pending.txt`.
- `daily_summary.py` restores monitor state, runs all monitor scripts, writes the report and updated state to MongoDB, then sends the assembled report through configured delivery.
- For Claude Code, keep the changelog visible but separate feature changes from fix/docs/chore items through the configured postprocessor.
