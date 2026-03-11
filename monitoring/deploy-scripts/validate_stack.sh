#!/bin/bash
set -euo pipefail

check() {
  local url="$1"
  local name="$2"
  for i in $(seq 1 30); do
    if curl -4 -fsS --connect-timeout 2 --max-time 5 "$url" >/dev/null; then
      echo "[monitoring-deploy] ${name} OK"
      return 0
    fi
    sleep 2
  done
  echo "[monitoring-deploy] ${name} FAIL: ${url}"
  return 1
}

check "http://127.0.0.1:9090/-/ready" "prometheus"
check "http://127.0.0.1:3000/api/health" "grafana"
check "http://127.0.0.1:9093/-/ready" "alertmanager"
check "http://127.0.0.1:3100/ready" "loki"
