#!/bin/bash
set -euo pipefail

CONFIG_FILE_PRIMARY="/home/ubuntu/analysis/codedeploy-bundle/deploy.env"
CONFIG_FILE_FALLBACK="/home/ubuntu/analysis/shared/deploy.env"
HOST_PORT="8000"
HEALTH_PATH="/"
HEALTH_HOST="127.0.0.1"
CONTAINER_NAME="analysis_ai"
HEALTH_MAX_RETRIES="60"
HEALTH_INTERVAL_SECONDS="3"

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
HEALTH_HOST="${HEALTH_HOST:-127.0.0.1}"
CONTAINER_NAME="${CONTAINER_NAME:-analysis_ai}"
HEALTH_MAX_RETRIES="${HEALTH_MAX_RETRIES:-20}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-3}"
HEALTH_URL="http://${HEALTH_HOST}:${HOST_PORT}${HEALTH_PATH}"

# Blue/Green green instance warm-up can take longer depending on image pull/startup.
for ((i=1; i<=HEALTH_MAX_RETRIES; i++)); do
  if curl -4 -fsS --connect-timeout 2 --max-time 5 "$HEALTH_URL" | grep -Eqi "healthy|ok|up"; then
    echo "[deploy] health check passed: $HEALTH_URL"
    exit 0
  fi
  sleep "$HEALTH_INTERVAL_SECONDS"
done

echo "[deploy] health check failed: $HEALTH_URL"
docker logs --tail 120 "$CONTAINER_NAME" 2>/dev/null || true
exit 1
