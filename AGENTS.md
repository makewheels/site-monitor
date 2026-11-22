# Agent Workflow

This repository is one product with three independently testable modules:

- `monitor/`: daily collection, report formatting, MongoDB persistence, and Feishu delivery.
- `cloud/`: Alibaba Cloud Function Compute API for Android history and app updates.
- `android/`: native Android reader and OSS release tooling.

Use `uv` for Python and `pnpm` for Node. Do not use pip, venv, Poetry, npm, or Yarn.

## Monitor

- The configured sources are GitHub Trending, Anthropic Engineering, and Geekbang AI curriculum courses. Do not re-add RSS feeds, blog sources, or the Codex radar without an explicit request.
- Keep feed, API, and RSSHub URLs in `monitor/config.json`.
- Read source configuration through `site_monitor.monitor_config`; do not hardcode source URLs in collectors.
- Keep collector code under `monitor/src/site_monitor/` and offline tests under `monitor/tests/`.
- Every new source needs a `Topic` entry in `report_payload.py` and a matching collector in `daily_summary.CHECK_MODULES`.
- Keep model access provider-neutral through `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`; `DASHSCOPE_API_KEY` is a compatibility fallback only.
- Enrich only newly discovered blog articles. Persist both `translated_title` and `summary_zh`, plus the original title/excerpt and model metadata, before MongoDB and Feishu delivery.
- Runtime files belong under `monitor/runtime/` and must not be committed. Geekbang course ID state is the exception and lives in the committed `monitor/data/geekbang_ai_courses.json`, updated by the daily workflow.

## Delivery And Schedule

- `.github/workflows/daily-monitor.yml` is the production scheduler.
- The schedule is 05:30 `Asia/Shanghai`; all configured sources are collected once per day.
- `weekly-trending.yml` runs on Saturday 09:00 `Asia/Shanghai` and pushes the weekly Trending top 10.
- Workflows are dispatched by the server-side systemd timers; the repository keeps no cron trigger.
- The daily workflow has contents write permission to commit the Geekbang course ID state JSON after successful delivery. Production delivery uses the Feishu Open API from `monitor/src/site_monitor/delivery.py`.
- Monitor state and structured reports are persisted to MongoDB before delivery.
- The application connects through the dedicated `site_monitor_app` account. Root credentials are administration-only.

## Cloud

- Keep API code in `cloud/src/site_monitor_cloud/` and offline tests in `cloud/tests/`.
- Public FC deployment settings live in `cloud/deploy/fc-config.json`.
- Root `s.yaml` is the Serverless Devs description for associating the existing function with Alibaba Cloud Serverless Application Center. Keep secrets out of it.
- FC secrets and release metadata are environment variables; `cloud/deploy/fc-env.example` contains names only.
- `cloud/scripts/deploy_fc.sh` updates code without replacing FC environment variables.
- Android authenticates with a read-only app token and never connects directly to MongoDB.
- Daily history must be sorted newest-first and deduplicated by report date.

## Android

- Public app version, API base URL, and OSS paths live in `android/release-config.json`.
- Published version history lives in `android/releases.json`, sorted by `published_at` descending.
- Keep signing keys and passwords outside the repository.
- `android/scripts/release.sh` builds a signed APK, uploads both versioned and stable-latest objects, and updates the release index.
- Keep UI and formatter tests under `android/app/src/test/`.

## Secrets

Never commit or print MongoDB URIs, passwords, server addresses, API keys, Feishu secrets, app/upload tokens, or Android signing credentials. Public FC and OSS HTTPS endpoints may be tracked in their designated JSON configuration files.

- Store monitor, Feishu, MongoDB, app, and upload credentials in Infisical `tools/dev/site-monitor`.
- Store the shared model credential in `common/dev/llm/site-monitor`; consumers load it after the app project so it overrides compatibility aliases.
- GitHub Actions authenticates with repository/ref/audience-bound OIDC and must not retain business GitHub Secrets.
- FC environment variables are runtime mirrors, not an independent source of truth. Verify them against Infisical after every rotation.
- Local development uses `infisical run`; do not recreate `monitor/.env` with real values.

## Verification

Run all module checks before committing:

```bash
cd monitor
uv run python -m json.tool config.json >/dev/null
uv run python -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
uv run pytest

cd ../cloud
uv run pytest
./scripts/build_fc_package.sh

cd ../android
./gradlew testReleaseUnitTest assembleRelease
```
