#!/bin/bash
set -euo pipefail

ANALYSIS_DIR="/home/ubuntu/analysis"
RUNTIME_DIR="${ANALYSIS_DIR}/runtime"
PROMTAIL_DIR="${RUNTIME_DIR}/promtail"
SHARED_DIR="${ANALYSIS_DIR}/shared"
BUNDLE_DIR="${ANALYSIS_DIR}/codedeploy-bundle"
APP_DIR="/home/ubuntu/app"

mkdir -p "$ANALYSIS_DIR" "$RUNTIME_DIR" "$PROMTAIL_DIR" "$SHARED_DIR" "$BUNDLE_DIR" "$APP_DIR"
chown -R ubuntu:ubuntu "$ANALYSIS_DIR" "$APP_DIR"
chmod 755 "$ANALYSIS_DIR" "$RUNTIME_DIR" "$PROMTAIL_DIR" "$SHARED_DIR" "$BUNDLE_DIR" "$APP_DIR"
