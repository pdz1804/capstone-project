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
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

exec python -m uvicorn --app-dir "$APP_DIR" server:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
