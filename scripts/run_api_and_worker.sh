#!/bin/sh
set -eu

APP_PORT="${APP_PORT:-8000}"

python -m app.workers.ai_worker &
WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}" &
API_PID=$!

term() {
  kill -TERM "$WORKER_PID" "$API_PID" 2>/dev/null || true
}

trap term INT TERM

while :; do
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    wait "$WORKER_PID" || true
    term
    wait "$API_PID" 2>/dev/null || true
    exit 1
  fi

  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID" || true
    term
    wait "$WORKER_PID" 2>/dev/null || true
    exit 1
  fi

  sleep 2
done
