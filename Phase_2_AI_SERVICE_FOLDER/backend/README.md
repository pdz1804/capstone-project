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

## Run locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env            # fill OPENAI_API_KEY, Qdrant, optional SageMaker
python run_api.py
```

Open `http://localhost:8000/docs` for OpenAPI.

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
