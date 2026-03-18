#!/bin/bash
set -euo pipefail

CONFIG_FILE_PRIMARY="/home/ubuntu/analysis/codedeploy-bundle/deploy.env"
CONFIG_FILE_FALLBACK="/home/ubuntu/analysis/shared/deploy.env"
CONTAINER_NAME="analysis_api_server"

if [ -f "$CONFIG_FILE_PRIMARY" ]; then
  CONFIG_FILE="$CONFIG_FILE_PRIMARY"
elif [ -f "$CONFIG_FILE_FALLBACK" ]; then
  CONFIG_FILE="$CONFIG_FILE_FALLBACK"
else
  CONFIG_FILE=""
fi

if [ -n "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

CONTAINER_NAME="${CONTAINER_NAME:-analysis_api_server}"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
