#!/bin/bash
set -euo pipefail

CONFIG_FILE_PRIMARY="/home/ubuntu/analysis/codedeploy-bundle/deploy.env"
CONFIG_FILE_FALLBACK="/home/ubuntu/analysis/shared/deploy.env"
HOST_PORT="8000"
HEALTH_PATH="/"

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

HOST_PORT="${HOST_PORT:-8000}"
HEALTH_PATH="${HEALTH_PATH:-/}"
HEALTH_URL="http://localhost:${HOST_PORT}${HEALTH_PATH}"

for i in {1..20}; do
  if curl -fsS "$HEALTH_URL" | grep -qi "healthy"; then
    echo "[deploy] health check passed: $HEALTH_URL"
    exit 0
  fi
  sleep 3
done

echo "[deploy] health check failed: $HEALTH_URL"
exit 1
