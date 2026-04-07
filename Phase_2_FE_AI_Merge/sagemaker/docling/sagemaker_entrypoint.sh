#!/bin/bash
set -euo pipefail

if [ "$#" -gt 0 ] && [ "$1" != "serve" ]; then
  exec "$@"
fi

export SAGEMAKER_SERVICE_MODE=true
exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
