#!/bin/bash
set -euo pipefail

BUNDLE_DIR="${BUNDLE_DIR:-/home/ubuntu/monitoring/codedeploy-bundle}"
CONFIG_FILE_PRIMARY="${BUNDLE_DIR}/deploy.env"
CONFIG_FILE_FALLBACK="/home/ubuntu/monitoring/shared/deploy.env"
COMPOSE_FILE="${BUNDLE_DIR}/docker-compose.monitoring.yml"
PROM_TEMPLATE="${BUNDLE_DIR}/prometheus/prometheus.remote.yml"
PROM_RENDERED="${BUNDLE_DIR}/prometheus/prometheus.rendered.yml"
ALERT_TEMPLATE_NOOP="${BUNDLE_DIR}/alertmanager/alertmanager.yml"
ALERT_TEMPLATE_DISCORD="${BUNDLE_DIR}/alertmanager/alertmanager.template.yml"
ALERT_RENDERED="${BUNDLE_DIR}/alertmanager/alertmanager.rendered.yml"

if [ -f "$CONFIG_FILE_PRIMARY" ]; then
  CONFIG_FILE="$CONFIG_FILE_PRIMARY"
elif [ -f "$CONFIG_FILE_FALLBACK" ]; then
  CONFIG_FILE="$CONFIG_FILE_FALLBACK"
else
  echo "[monitoring-deploy] missing config file"
  echo "[monitoring-deploy] checked: $CONFIG_FILE_PRIMARY and $CONFIG_FILE_FALLBACK"
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MONITORING_EC2_TAG_KEY="${MONITORING_EC2_TAG_KEY:-MonitoringTarget}"
MONITORING_EC2_TAG_VALUE="${MONITORING_EC2_TAG_VALUE:-analysis}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

if [ ! -f "$PROM_TEMPLATE" ]; then
  echo "[monitoring-deploy] prometheus template not found: $PROM_TEMPLATE"
  exit 1
fi

cp "$PROM_TEMPLATE" "$PROM_RENDERED"
sed -i "s/__AWS_REGION__/${AWS_REGION}/g" "$PROM_RENDERED"
sed -i "s/__EC2_TAG_KEY__/${MONITORING_EC2_TAG_KEY}/g" "$PROM_RENDERED"
sed -i "s/__EC2_TAG_VALUE__/${MONITORING_EC2_TAG_VALUE}/g" "$PROM_RENDERED"
cp "$PROM_RENDERED" "${BUNDLE_DIR}/prometheus/prometheus.remote.yml"

if [ -n "$DISCORD_WEBHOOK_URL" ] && [ -f "$ALERT_TEMPLATE_DISCORD" ]; then
  cp "$ALERT_TEMPLATE_DISCORD" "$ALERT_RENDERED"
  sed -i "s|__DISCORD_WEBHOOK_URL__|${DISCORD_WEBHOOK_URL}|g" "$ALERT_RENDERED"
  cp "$ALERT_RENDERED" "${BUNDLE_DIR}/alertmanager/alertmanager.yml"
elif [ -f "$ALERT_TEMPLATE_NOOP" ]; then
  cp "$ALERT_TEMPLATE_NOOP" "$ALERT_RENDERED"
  cp "$ALERT_RENDERED" "${BUNDLE_DIR}/alertmanager/alertmanager.yml"
  echo "[monitoring-deploy] DISCORD_WEBHOOK_URL is empty; keeping Alertmanager receiver as noop"
fi

docker compose -f "$COMPOSE_FILE" --env-file "$CONFIG_FILE" pull || true
docker compose -f "$COMPOSE_FILE" --env-file "$CONFIG_FILE" up -d
