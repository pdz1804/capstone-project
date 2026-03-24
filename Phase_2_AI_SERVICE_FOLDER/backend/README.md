# Phase 2 AI Service — Backend

## Architecture

```
app/
  api/routes/          # FastAPI routers (thin)
  services/            # Business logic: indexing, search, processing, insights
  repositories/        # Qdrant clients, BM25 persistence
  core/paths.py        # Paths + YAML merge with env
src/                   # Legacy pipeline: processor, chunking, retrieval helpers, generation
config/default.yaml    # Pipeline + Qdrant + inference settings
```

- **Dense text retrieval** uses **Qdrant** (cosine on `sentence-transformers` embeddings).
- **BM25** uses an on-disk pickle (`output/retrieval/bm25_index.pkl`) built from the same chunks as Qdrant.
- **Hybrid** fuses BM25 + dense (Qdrant) with weight `inference.hybrid_alpha` (default 0.5).
- **Image retrieval** stores **ColQwen multivectors** in Qdrant (MaxSim), same idea as `Phase_2_PDZ_003_Test_Qdrant_Cloud`.

## Install dependencies into `myenv` (recommended for this repo)

Your project venv is expected at **`Code/myenv`** (same level as `Phase_2_AI_SERVICE_FOLDER`), matching paths like `Code\myenv\Lib\site-packages`.

**PowerShell** (from `Phase_2_AI_SERVICE_FOLDER/backend`):

```powershell
.\install_requirements.ps1
```

**CMD**:

```bat
install_requirements.bat
```

**Manual one-liner** (adjust drive/path if your `Code` folder differs):

```powershell
& "D:\PDZ\BKU\Learning\LVTN\GD1\Code\myenv\Scripts\python.exe" -m pip install -r requirements.txt
```

If `myenv` lives elsewhere, set **`MYENV_PYTHON`** to that `python.exe`, then run `install_requirements.ps1` again.

Always prefer **`python -m pip`** for the venv you intend — avoid a global `pip` that points at another Python.

## Run locally

```powershell
cd Phase_2_AI_SERVICE_FOLDER\backend
# Activate myenv first (from Code folder):
..\..\myenv\Scripts\Activate.ps1
python run_api.py
```

Or without activating, run the API with the full interpreter:

```powershell
& "..\..\myenv\Scripts\python.exe" run_api.py
```

```bash
cd backend
copy .env.example .env            # fill OPENAI_API_KEY, Qdrant, optional SageMaker
```

Open `http://localhost:8000/docs` for OpenAPI.

## Unit tests

Tests live under `tests/` (`api/` for route smoke tests with mocks, `services/` for core settings, Qdrant factory, ColQwen inference flags). Run from **`backend`** using the same **`myenv`** interpreter as install.

**PowerShell**

```powershell
.\run_tests.ps1
```

**CMD**

```bat
run_tests.bat
```

**Manual**

```powershell
& "..\..\myenv\Scripts\python.exe" -m pytest tests\ -v
```

Optional: `pytest -m unit` (markers in `pytest.ini`). Pass extra pytest args to the scripts, e.g. `.\run_tests.ps1 tests\services -q`.

## Indexing workflow

1. `POST /api/upload` — files into `input/`.
2. `POST /api/process` — normalization → `output/processing/stage4_rag_ready/`.
3. `POST /api/index` or `POST /api/index/text` + `POST /api/index/image` — builds Qdrant + `documents.json` + BM25.

## Inference: local vs SageMaker

Set in **environment** (recommended) or `config/default.yaml` under `inference`:

| Variable | Meaning |
|----------|---------|
| `USE_AWS_SAGEMAKER_INFERENCE=true` | Use **SageMaker Runtime** for ColQwen `embed-query` / `embed-images` (JSON contract matches `Phase_2_PDZ_002_Model_Deploy/server.py`). |
| `AWS_REGION` | e.g. `us-west-2` |
| `SAGEMAKER_ENDPOINT_NAME` | e.g. `phase2-colqwen-rt` |

When `false`, ColQwen loads locally (GPU/CPU) via `colpali-engine`.

Probe: `GET /api/system/inference`.

## Docker

```bash
docker build -t phase2-ai-backend .
docker run -p 8000:8000 --env-file .env phase2-ai-backend
```
