#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CONFIG_FILE="$ROOT_DIR/release-config.json"
INDEX_FILE="$ROOT_DIR/releases.json"
APK_FILE="$ROOT_DIR/app/build/outputs/apk/release/app-release.apk"
KEYSTORE="${SITE_MONITOR_ANDROID_KEYSTORE:-$HOME/.config/site-monitor/android-release.jks}"
KEY_ALIAS="${SITE_MONITOR_ANDROID_KEY_ALIAS:-ai-monitor}"

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
TASK_TMP_ROOT=$(cd "$TASK_TMP_ROOT" && pwd -P)
TASK_TMP_DIR=$(mktemp -d "$TASK_TMP_ROOT/site-monitor-android-release.XXXXXX")
cleanup_task_tmp() {
  local resolved=""
  resolved=$(cd "$TASK_TMP_DIR" 2>/dev/null && pwd -P) || return 0
  case "$resolved" in
    "$TASK_TMP_ROOT"/site-monitor-android-release.*) ;;
    *) printf 'Refusing to clean unexpected temp path: %s\n' "$resolved" >&2; return 1 ;;
  esac
  [[ ! -L "$resolved" ]] || return 1
  find "$resolved" -xdev -depth -delete
}
trap cleanup_task_tmp EXIT INT TERM

version_code=$(jq -r '.version_code' "$CONFIG_FILE")
version_name=$(jq -r '.version_name' "$CONFIG_FILE")
api_url=$(jq -r '.api_base_url' "$CONFIG_FILE")
bucket=$(jq -r '.distribution.bucket' "$CONFIG_FILE")
prefix=$(jq -r '.distribution.object_prefix' "$CONFIG_FILE")
public_base_url=$(jq -r '.distribution.public_base_url' "$CONFIG_FILE")
region=$(jq -r '.distribution.region' "$CONFIG_FILE")
apk_url="$public_base_url/ai-monitor-$version_name.apk"
release_notes=$(jq -r '.release_notes' "$CONFIG_FILE")
published_at=$(date -Iseconds)

app_token=${SITE_MONITOR_ANDROID_APP_TOKEN:-$(security find-generic-password -w -a "$USER" -s site-monitor-android-app-token)}
keystore_password=${SITE_MONITOR_ANDROID_KEYSTORE_PASSWORD:-$(security find-generic-password -w -a "$USER" -s site-monitor-android-keystore)}

SITE_MONITOR_ANDROID_API_URL="$api_url" \
SITE_MONITOR_ANDROID_APP_TOKEN="$app_token" \
SITE_MONITOR_ANDROID_KEYSTORE="$KEYSTORE" \
SITE_MONITOR_ANDROID_KEYSTORE_PASSWORD="$keystore_password" \
SITE_MONITOR_ANDROID_KEY_ALIAS="$KEY_ALIAS" \
SITE_MONITOR_ANDROID_KEY_PASSWORD="$keystore_password" \
  "$ROOT_DIR/gradlew" -p "$ROOT_DIR" clean testReleaseUnitTest assembleRelease

sha256=$(shasum -a 256 "$APK_FILE" | awk '{print $1}')
tmp_config="$TASK_TMP_DIR/release-config.json"
jq \
  --arg published_at "$published_at" \
  --arg apk_url "$apk_url" \
  '.published_at = $published_at | .distribution.versioned_apk_url = $apk_url' \
  "$CONFIG_FILE" > "$tmp_config"
mv "$tmp_config" "$CONFIG_FILE"

tmp_index="$TASK_TMP_DIR/releases.json"
jq \
  --argjson version_code "$version_code" \
  --arg version_name "$version_name" \
  --arg published_at "$published_at" \
  --arg apk_url "$apk_url" \
  --arg sha256 "$sha256" \
  --arg release_notes "$release_notes" \
  '.generated_at = $published_at
   | .releases = ([{
       version_code: $version_code,
       version_name: $version_name,
       published_at: $published_at,
       apk_url: $apk_url,
       sha256: $sha256,
       release_notes: $release_notes
     }] + [.releases[] | select(.version_code != $version_code)]
     | sort_by(.published_at) | reverse)' \
  "$INDEX_FILE" > "$tmp_index"
mv "$tmp_index" "$INDEX_FILE"

aliyun oss cp "$APK_FILE" "oss://$bucket/$prefix/ai-monitor-$version_name.apk" --force --region "$region"
aliyun oss cp "$APK_FILE" "oss://$bucket/$prefix/ai-monitor-latest.apk" --force --region "$region"
aliyun oss cp "$INDEX_FILE" "oss://$bucket/$prefix/releases.json" --force --region "$region"

curl --fail --silent --show-error --head "$apk_url" >/dev/null
printf 'Released AI Monitor %s (%s)\n%s\n' "$version_name" "$version_code" "$apk_url"
