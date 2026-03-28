#!/usr/bin/env bash
# Phase_2_FE_AI_Merge — venv, pip, npm, pytest (macOS / Linux / WSL)
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#   ./scripts/setup.sh --skip-tests
#   ./scripts/setup.sh --skip-frontend

set -euo pipefail
SKIP_TESTS=0
SKIP_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

echo "==> Backend venv: $VENV"
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

echo "==> pip install (backend)"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$BACKEND/requirements.txt"

if [[ "$SKIP_FRONTEND" -eq 0 && -d "$FRONTEND" ]]; then
  echo "==> npm install (frontend)"
  (cd "$FRONTEND" && npm install)
fi

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  echo "==> pytest"
  (cd "$BACKEND" && "$VENV/bin/python" -m pytest tests -q --tb=short)
fi

echo "Done. Activate: source $VENV/bin/activate"
echo "API: cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "UI:  cd frontend && npm run dev"
