#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
BUILD_DIR="$ROOT_DIR/.build/package"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$ROOT_DIR/.build" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

uv pip install \
  --target "$BUILD_DIR" \
  --python-version 3.10 \
  --python-platform x86_64-manylinux_2_17 \
  --only-binary :all: \
  --requirements "$ROOT_DIR/deploy/requirements.txt"

cp -R "$ROOT_DIR/src/site_monitor_cloud" "$BUILD_DIR/site_monitor_cloud"
cp "$ROOT_DIR/app.py" "$BUILD_DIR/app.py"

(
  cd "$BUILD_DIR"
  zip -qr "$DIST_DIR/site-monitor-cloud.zip" .
)

printf '%s\n' "$DIST_DIR/site-monitor-cloud.zip"
