#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE_PRIMARY="/home/ubuntu/analysis/codedeploy-bundle/deploy.env"
CONFIG_FILE_FALLBACK="/home/ubuntu/analysis/shared/deploy.env"
APP_ENV_FILE_PRIMARY="/home/ubuntu/app/.env"
APP_ENV_FILE_FALLBACK="/home/ubuntu/analysis/shared/.env"
RUNTIME_DIR="/home/ubuntu/analysis/runtime"
PROMTAIL_RUNTIME_DIR="${RUNTIME_DIR}/promtail"
EXPORTER_COMPOSE_FILE="${BUNDLE_ROOT}/monitoring/analysis-exporters.compose.yml"

if [ -f "$CONFIG_FILE_PRIMARY" ]; then
  CONFIG_FILE="$CONFIG_FILE_PRIMARY"
elif [ -f "$CONFIG_FILE_FALLBACK" ]; then
  CONFIG_FILE="$CONFIG_FILE_FALLBACK"
else
  echo "[deploy] missing config file"
  echo "[deploy] checked: $CONFIG_FILE_PRIMARY and $CONFIG_FILE_FALLBACK"
  echo "[deploy] required keys: ECR_REGISTRY, ECR_REPO (optional: DEPLOY_TAG, CONTAINER_NAME, HOST_PORT, APP_PORT, AWS_REGION)"
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
DEPLOY_TAG="${DEPLOY_TAG:-dev}"
CONTAINER_NAME="${CONTAINER_NAME:-analysis_api_server}"
HOST_PORT="${HOST_PORT:-8000}"
APP_PORT="${APP_PORT:-8000}"
SSM_PARAM_NAME="${SSM_PARAM_NAME:-}"

: "${ECR_REGISTRY:?ECR_REGISTRY is required in $CONFIG_FILE}"
: "${ECR_REPO:?ECR_REPO is required in $CONFIG_FILE}"

IMAGE_URI="${ECR_REGISTRY}/${ECR_REPO}:${DEPLOY_TAG}"

echo "[deploy] image: ${IMAGE_URI}"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker pull "$IMAGE_URI"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

# Refresh runtime env from Parameter Store on every deployment.
if [ -n "$SSM_PARAM_NAME" ]; then
  mkdir -p "$(dirname "$APP_ENV_FILE_PRIMARY")"
  aws ssm get-parameter \
    --name "$SSM_PARAM_NAME" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --region "$AWS_REGION" \
    > "$APP_ENV_FILE_PRIMARY"
fi

DOCKER_ENV_ARGS=()
if [ -f "$APP_ENV_FILE_PRIMARY" ]; then
  DOCKER_ENV_ARGS+=(--env-file "$APP_ENV_FILE_PRIMARY")
elif [ -f "$APP_ENV_FILE_FALLBACK" ]; then
  mkdir -p "$(dirname "$APP_ENV_FILE_PRIMARY")"
  cp "$APP_ENV_FILE_FALLBACK" "$APP_ENV_FILE_PRIMARY"
  DOCKER_ENV_ARGS+=(--env-file "$APP_ENV_FILE_PRIMARY")
fi

mkdir -p "$PROMTAIL_RUNTIME_DIR"

MONITOR_HOSTNAME="$(hostname | grep -oE '[0-9]+(-[0-9]+){3}' | sed 's/-/./g; s/$/:9080/')"
if [[ -z "$MONITOR_HOSTNAME" ]]; then
  MONITOR_HOSTNAME="$(hostname)"
fi

if [ -f "$APP_ENV_FILE_PRIMARY" ]; then
  if grep -q '^monitor_hostname=' "$APP_ENV_FILE_PRIMARY"; then
    sed -i "s/^monitor_hostname=.*/monitor_hostname=${MONITOR_HOSTNAME}/" "$APP_ENV_FILE_PRIMARY"
  else
    echo "monitor_hostname=${MONITOR_HOSTNAME}" >> "$APP_ENV_FILE_PRIMARY"
  fi
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${HOST_PORT}:${APP_PORT}" \
  "${DOCKER_ENV_ARGS[@]}" \
  "$IMAGE_URI"

if [ -f "$EXPORTER_COMPOSE_FILE" ]; then
  if command -v docker-compose >/dev/null 2>&1; then
    EXPORTER_COMPOSE="docker-compose"
  else
    EXPORTER_COMPOSE="docker compose"
  fi

  ENV_FILE_FOR_EXPORTERS="$APP_ENV_FILE_PRIMARY"
  if [ ! -f "$ENV_FILE_FOR_EXPORTERS" ] && [ -f "$APP_ENV_FILE_FALLBACK" ]; then
    ENV_FILE_FOR_EXPORTERS="$APP_ENV_FILE_FALLBACK"
  fi

  if [ -f "$ENV_FILE_FOR_EXPORTERS" ]; then
    $EXPORTER_COMPOSE -f "$EXPORTER_COMPOSE_FILE" --env-file "$ENV_FILE_FOR_EXPORTERS" up -d
  else
    $EXPORTER_COMPOSE -f "$EXPORTER_COMPOSE_FILE" up -d
  fi
fi

docker image prune -f >/dev/null 2>&1 || true
