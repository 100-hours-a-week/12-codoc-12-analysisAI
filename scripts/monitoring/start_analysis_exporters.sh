#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="${BASE_DIR}/monitoring/analysis-exporters.compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "[monitoring] compose file not found: $COMPOSE_FILE"
  exit 1
fi

if [ "${1:-}" = "--gpu" ]; then
  docker compose -f "$COMPOSE_FILE" --profile gpu up -d
else
  docker compose -f "$COMPOSE_FILE" up -d
fi

echo "[monitoring] analysis exporters started"
