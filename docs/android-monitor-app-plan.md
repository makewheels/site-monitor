# Android Monitor App Plan

## Decisions

- First version is an Android read app, not a push-notification app.
- The phone has no Google services, so FCM is not the default path.
- The user will actively open the app to read the latest monitor result.
- The backend uses the user's own MongoDB on the existing Tencent Cloud setup.
- GitHub Actions deploys the cloud API to Tencent Cloud.
- Existing Hermes Weixin delivery stays available during the transition.
- Secrets stay in local env, server env, or GitHub Secrets; they must not be written to `config.json`.

## Product Shape

The app is a dense monitor reader named `AI Monitor`.

- Before native Android implementation, use `docs/android-monitor-app-mockup.html` as the visual reference for layout, density, topic grouping, and history behavior.
- Today page: latest report, grouped by topic.
- Topic tabs: All, Claude, GitHub, OpenAI, Anthropic, LangChain, Copilot.
- History page: total history by date, with topic filtering.
- Detail page: full section content and links.
- Settings page: cloud API address, manual sync, cache cleanup, version.
- Offline mode: show cached data and mark it as offline cache.

History is stored together, not as one database/table per topic. Each item carries a `topic` field, so the app can show both total history and per-topic history.

## Data Model

Use MongoDB collections:

- `reports`: one document per daily report run.
- `report_items`: one document per topic/section inside a report.

First-version topic keys:

- `github_trending`
- `anthropic_engineering`
- `openai_engineering`
- `langchain_blog`
- `claude_code`
- `github_copilot_cli`

Each `report_item` should include at least:

- `report_id`
- `topic`
- `topic_name`
- `date`
- `title`
- `body`
- `links`
- `created_at`

## Cloud API

Create a new cloud API separate from the existing local Flask management UI.

- `POST /api/v1/reports`: Mac uploads structured reports. Auth: `X-Site-Monitor-Upload-Token`.
- `GET /api/v1/reports/latest`: Android gets latest report grouped by topic.
- `GET /api/v1/reports?limit=30&topic=claude_code`: Android lists history.
- `GET /api/v1/reports/<report_id>`: Android gets full report detail.
- `GET /api/v1/topics`: Android gets topic names and ordering.
- `GET /healthz`: deployment health check.

Android uses a read-only `X-Site-Monitor-App-Token`. MongoDB is never exposed directly to Android.

## Site Monitor Changes

- Split `daily_summary.py` report assembly into text output and structured payload output.
- Extend `delivery.py` with fanout delivery.
- Add a `cloud_api` delivery provider that uploads the structured report to Tencent Cloud.
- If cloud sync fails, keep the generated report and Weixin send working.
- Save failed sync payloads under `runtime/pending/cloud_sync/` for retry.

## Deployment

Local development:

- Python API uses `SITE_MONITOR_MONGO_URI=mongodb://127.0.0.1:27017/site_monitor_dev` by default.
- Tests must not call real RSSHub, GitHub, vendor pages, or production MongoDB.
- Android debug builds can point to a local/test API base URL.

Tencent Cloud:

- Run the API with gunicorn and systemd.
- Put Nginx in front for HTTPS.
- Store server env outside the repo:
  - `SITE_MONITOR_MONGO_URI`
  - `SITE_MONITOR_DB_NAME`
  - `SITE_MONITOR_UPLOAD_TOKEN`
  - `SITE_MONITOR_APP_TOKEN`
  - `SITE_MONITOR_ALLOWED_ORIGINS`

GitHub Actions:

- Use SSH/rsync or SSH git pull to deploy to Tencent Cloud.
- Store host, user, private key, deploy path, and env as GitHub Secrets.
- Restart the systemd service after deploy.
- Verify `/healthz` after deploy.

Implemented first-version files:

- Cloud API entry: `src/site_monitor/cloud_api.py`
- Structured report payload: `src/site_monitor/report_payload.py`
- Android project: `android/`
- Tencent Cloud templates: `deploy/`
- GitHub Actions workflow: `.github/workflows/deploy-tencent-cloud.yml`

## Open Questions

- Confirm the exact Tencent Cloud host, deploy path, domain, and existing MongoDB URI during implementation.
- Decide whether Android release APK should be built locally only or also by GitHub Actions.
- Decide later whether push notifications are still needed after the read-first app is usable.
