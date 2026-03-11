#!/bin/bash
set -euo pipefail

BUNDLE_DIR="/home/ubuntu/monitoring/codedeploy-bundle"
COMPOSE_FILE="${BUNDLE_DIR}/docker-compose.monitoring.yml"

if [ -f "$COMPOSE_FILE" ]; then
  docker compose -f "$COMPOSE_FILE" down || true
fi
