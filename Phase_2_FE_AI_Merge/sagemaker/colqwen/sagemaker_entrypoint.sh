#!/bin/bash
set -euo pipefail

if [ "$#" -gt 0 ] && [ "$1" != "serve" ]; then
  exec "$@"
fi

export SAGEMAKER_SERVICE_MODE=true
export COLQWEN_MODEL="${COLQWEN_MODEL:-vidore/colqwen2-v1.0}"
export COLQWEN_QUANTIZATION="${COLQWEN_QUANTIZATION:-8bit}"
export COLQWEN_MAX_CONCURRENT_INFERENCES="${COLQWEN_MAX_CONCURRENT_INFERENCES:-2}"

exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
