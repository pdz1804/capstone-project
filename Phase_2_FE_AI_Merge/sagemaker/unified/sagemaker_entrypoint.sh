#!/bin/bash
set -euo pipefail

if [ "$#" -gt 0 ] && [ "$1" != "serve" ]; then
  exec "$@"
fi

APP_DIR="${APP_DIR:-/opt/program}"
if [ ! -d "$APP_DIR" ]; then
  echo "FATAL: APP_DIR does not exist: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
if [ ! -f "$APP_DIR/server.py" ]; then
  echo "FATAL: server.py not found at $APP_DIR/server.py"
  exit 1
fi

export AWS_REGION="${AWS_REGION:-us-west-2}"
export SAGEMAKER_SERVICE_MODE=true
export UNIFIED_MAX_CONCURRENT_GPU_OPS="${UNIFIED_MAX_CONCURRENT_GPU_OPS:-10}"
export COLQWEN_MAX_CONCURRENT_INFERENCES="${COLQWEN_MAX_CONCURRENT_INFERENCES:-10}"
export PYTHONPATH="$APP_DIR:$APP_DIR/backend:$APP_DIR/backend/src:${PYTHONPATH:-}"

exec python -m uvicorn --app-dir "$APP_DIR" server:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
