#!/bin/sh
set -eu

APP_PORT="${APP_PORT:-8000}"

python -m app.workers.ai_worker &
AI_WORKER_PID=$!

python -m app.workers.ocr_worker &
OCR_WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}" &
API_PID=$!

term() {
  kill -TERM "$AI_WORKER_PID" "$OCR_WORKER_PID" "$API_PID" 2>/dev/null || true
}

trap term INT TERM

while :; do
  if ! kill -0 "$AI_WORKER_PID" 2>/dev/null; then
    echo "[ai_worker] died, restarting..."
    python -m app.workers.ai_worker &
    AI_WORKER_PID=$!
  fi

  if ! kill -0 "$OCR_WORKER_PID" 2>/dev/null; then
    echo "[ocr_worker] died, restarting..."
    python -m app.workers.ocr_worker &
    OCR_WORKER_PID=$!
  fi

  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID" || true
    term
    wait "$AI_WORKER_PID" 2>/dev/null || true
    wait "$OCR_WORKER_PID" 2>/dev/null || true
    exit 1
  fi

  sleep 2
done
