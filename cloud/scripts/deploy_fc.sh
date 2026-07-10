#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CONFIG_FILE="$ROOT_DIR/deploy/fc-config.json"
ANDROID_CONFIG="$ROOT_DIR/../android/release-config.json"

region=$(jq -r '.region' "$CONFIG_FILE")
function_name=$(jq -r '.function_name' "$CONFIG_FILE")
bucket=$(jq -r '.code.bucket' "$CONFIG_FILE")
object=$(jq -r '.code.object' "$CONFIG_FILE")
api_base_url=$(jq -r '.api_base_url' "$ANDROID_CONFIG")

package=$($ROOT_DIR/scripts/build_fc_package.sh)
aliyun oss cp "$package" "oss://$bucket/$object" --force --region "$region"

body=$(jq -nc \
  --arg bucket "$bucket" \
  --arg object "$object" \
  '{code: {ossBucketName: $bucket, ossObjectName: $object}}')
aliyun fc UpdateFunction \
  --functionName "$function_name" \
  --region "$region" \
  --body "$body" >/dev/null

curl --fail --silent --show-error "$api_base_url/healthz" | jq -e '.ok == true' >/dev/null
printf 'Deployed %s to %s and verified /healthz\n' "$function_name" "$region"
