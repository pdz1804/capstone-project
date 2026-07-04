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

: "${RUN_ID:=pdf_dataset_eval_ocr_vlm_formula}"
: "${STAGE:=all}"
: "${RETRIEVER_TYPE:=hybrid}"
: "${TOP_K:=10}"
: "${K_VALUES:=1,3,5,10}"
: "${GENERATION_CONCURRENCY:=4}"
: "${JUDGE_CONCURRENCY:=8}"
: "${LLM_CONCURRENCY:=2}"
: "${MODEL:=zai.glm-4.7-flash}"
: "${PROVIDER:=}"
: "${PDF_CONTENT_SOURCE:=docling}"
: "${PDF_VLM_MODEL:=HuggingFaceTB/SmolVLM-256M-Instruct}"
: "${PDF_VLM_BATCH_SIZE:=4}"
: "${PDF_VLM_PAGE_FILTER:=visual_or_formula_pages}"
: "${PARSE_BATCH_SIZE:=1}"
: "${PARSE_BATCH_TIMEOUT_SECONDS:=7200}"
: "${PARSE_HEARTBEAT_SECONDS:=30}"
: "${SECTION_CAP:=120}"

cmd=(
  python backend/evals/retrieval/run_pdf_dataset_retrieval_eval.py
  --run-id "${RUN_ID}"
  --stage "${STAGE}"
  --retrieval-modalities text
  --retriever-type "${RETRIEVER_TYPE}"
  --top-k "${TOP_K}"
  --k-values "${K_VALUES}"
  --generation-concurrency "${GENERATION_CONCURRENCY}"
  --judge-concurrency "${JUDGE_CONCURRENCY}"
  --llm-concurrency "${LLM_CONCURRENCY}"
  --model "${MODEL}"
  --pdf-content-source "${PDF_CONTENT_SOURCE}"
  --enable-pdf-vlm
  --enable-pdf-formula-enrichment
  --pdf-vlm-model "${PDF_VLM_MODEL}"
  --pdf-vlm-batch-size "${PDF_VLM_BATCH_SIZE}"
  --pdf-vlm-page-filter "${PDF_VLM_PAGE_FILTER}"
  --parse-batch-size "${PARSE_BATCH_SIZE}"
  --parse-batch-timeout-seconds "${PARSE_BATCH_TIMEOUT_SECONDS}"
  --parse-heartbeat-seconds "${PARSE_HEARTBEAT_SECONDS}"
  --section-cap "${SECTION_CAP}"
  --resume
)

if [[ -n "${PROVIDER}" ]]; then
  cmd+=(--provider "${PROVIDER}")
fi

if [[ -n "${MAX_PDFS:-}" ]]; then
  cmd+=(--max-pdfs "${MAX_PDFS}")
fi

if [[ "${FORCE:-0}" == "1" ]]; then
  cmd+=(--force)
fi

cmd+=("$@")

echo "Running PDF text-score eval with OCR + VLM + formula enrichment..."
printf '  %q' "${cmd[@]}"
echo

"${cmd[@]}"

echo
echo "Text-score outputs:"
echo "  backend/evals/retrieval/results/${RUN_ID}/judgments_text.jsonl"
echo "  backend/evals/retrieval/results/${RUN_ID}/stage_retrieve_outputs_text.json"
echo "  backend/evals/retrieval/results/${RUN_ID}/stage_retrieve_stats_text.json"
echo "  backend/evals/retrieval/results/${RUN_ID}/report.json"
echo "  backend/evals/retrieval/results/${RUN_ID}/summary.md"
