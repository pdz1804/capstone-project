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

export SAGEMAKER_SERVICE_MODE=true
export COLQWEN_MODEL="${COLQWEN_MODEL:-vidore/colqwen2-v1.0}"
export COLQWEN_QUANTIZATION="${COLQWEN_QUANTIZATION:-8bit}"
export COLQWEN_MAX_CONCURRENT_INFERENCES="${COLQWEN_MAX_CONCURRENT_INFERENCES:-2}"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

exec python -m uvicorn --app-dir "$APP_DIR" server:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
