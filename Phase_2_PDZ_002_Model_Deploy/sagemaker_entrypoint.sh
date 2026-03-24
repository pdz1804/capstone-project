#!/bin/bash
set -e

# If a command is provided and it is not SageMaker's "serve", run it directly.
if [ "$#" -gt 0 ] && [ "$1" != "serve" ]; then
  exec "$@"
fi

export COLQWEN_MODEL="${COLQWEN_MODEL:-vidore/colqwen2-v1.0}"
export COLQWEN_QUANTIZATION="${COLQWEN_QUANTIZATION:-8bit}"
export COLQWEN_MAX_CONCURRENT_INFERENCES="${COLQWEN_MAX_CONCURRENT_INFERENCES:-2}"
export SAGEMAKER_SERVICE_MODE="true"

exec python /opt/program/server.py \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --model "${COLQWEN_MODEL}" \
  --quantization "${COLQWEN_QUANTIZATION}" \
  --max-concurrent-inferences "${COLQWEN_MAX_CONCURRENT_INFERENCES}" \
  --managed-runtime
