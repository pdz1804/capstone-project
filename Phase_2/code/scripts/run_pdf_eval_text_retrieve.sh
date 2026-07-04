#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_ACTIVATE="${REPO_ROOT}/../capstone/bin/activate"
if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "Cannot find venv: ${VENV_ACTIVATE}" >&2
  exit 1
fi

source "${VENV_ACTIVATE}"

: "${RETRIEVER_TYPE:=hybrid}"
: "${TOP_K:=10}"
: "${K_VALUES:=1,3,5,10}"
: "${JUDGE_CONCURRENCY:=8}"
: "${MODEL:=zai.glm-4.7-flash}"

cmd=(
  python backend/evals/retrieval/run_pdf_dataset_retrieval_eval.py
  --stage retrieve
  --retrieval-modalities text
  --retriever-type "${RETRIEVER_TYPE}"
  --top-k "${TOP_K}"
  --k-values "${K_VALUES}"
  --judge-concurrency "${JUDGE_CONCURRENCY}"
  --model "${MODEL}"
  --resume
)

if [[ -n "${PROVIDER:-}" ]]; then
  cmd+=(--provider "${PROVIDER}")
fi

if [[ "${FORCE:-0}" == "1" ]]; then
  cmd+=(--force)
fi

cmd+=("$@")

echo "Running text-only retrieval judge..."
printf '  %q' "${cmd[@]}"
echo

"${cmd[@]}"

echo
echo "Text retrieve outputs:"
echo "  backend/evals/retrieval/results/pdf_dataset_eval/judgments_text.jsonl"
echo "  backend/evals/retrieval/results/pdf_dataset_eval/stage_retrieve_outputs_text.json"
echo "  backend/evals/retrieval/results/pdf_dataset_eval/stage_retrieve_stats_text.json"
