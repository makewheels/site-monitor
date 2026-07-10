# Android Monitor App

## Current Architecture

- Native Android application ID: `com.makewheels.aimonitor`.
- Minimum SDK 24, target SDK 35.
- Alibaba Cloud Function Compute provides the authenticated history API.
- The existing MongoDB on the Tencent Cloud Lighthouse server remains the source of truth.
- Alibaba Cloud OSS stores versioned APKs, a stable latest APK, and `releases.json`.
- The phone never connects directly to MongoDB.

## Product Behavior

- Today: latest report grouped into topic sections.
- Topic tabs: all configured monitor topics, horizontally scrollable.
- History: one newest report per date, sorted descending; topic history uses the same rule.
- Articles: title, summary, visible URL, in-app WebView, and external-browser action.
- Offline: latest successful responses are cached locally.
- Settings: API status, last sync, manual update check, cache cleanup, and installed version.
- Updates: startup checks `/api/v1/app/releases/latest` and opens the OSS APK when a newer version exists.

## API Contract

- `POST /api/v1/reports`: monitor upload, authenticated by `X-Site-Monitor-Upload-Token`.
- `GET /api/v1/reports/latest`: latest structured report.
- `GET /api/v1/reports?limit=60&topic=...`: report or topic history.
- `GET /api/v1/reports/<report_id>`: report detail.
- `GET /api/v1/topics`: configured topic metadata.
- `GET /api/v1/app/releases/latest`: latest Android version and APK URL.
- `GET /healthz`: public health check.

All read endpoints except health use `X-Site-Monitor-App-Token`.

## Versioning And Distribution

`release-config.json` is the tracked public source of truth for application ID, version code, version name, API base URL, release notes, and OSS destinations. `releases.json` is append-only by version and sorted by publish time descending.

For each release, `scripts/release.sh` publishes:

- `ai-monitor-<version>.apk`: immutable version URL.
- `ai-monitor-latest.apk`: stable URL for the newest build.
- `releases.json`: all real published versions, newest first.

Signing material, app tokens, and passwords stay in environment variables or the macOS Keychain.
