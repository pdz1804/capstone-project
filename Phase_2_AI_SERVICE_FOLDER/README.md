# Phase 2 — AI Service (refactored)

This folder is the **refactored Phase 2** deliverable: a **layered backend** (API → Service → Repository → Qdrant + files), **Qdrant** as the vector database (no on-disk FAISS for dense text), **configurable ColQwen inference** (local GPU vs **AWS SageMaker** endpoint), and an updated **React** UI.

**Do not use** the Terraform tree under `Phase_2/terraform` for this refactor — it was left unchanged.

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI app (`app/`), legacy `src/` processors & generators, `config/default.yaml` |
| `frontend/` | Vite + React client (proxies `/api` to port 8000) |
| `docs/` | API schema and environment reference |

## Quick start

1. **Qdrant** — run Docker locally or point to Qdrant Cloud (see `docs/ENVIRONMENT.md` and `Phase_2_PDZ_003_Test_Qdrant_Cloud`).
2. **Backend** — `cd backend`, create venv, `pip install -r requirements.txt`, copy `.env.example` → `.env`, then `python run_api.py`.
3. **Frontend** — `cd frontend`, `npm install`, `npm run dev`.

## Documentation

- [Backend README](backend/README.md) — architecture, indexing, inference switch.
- [Frontend README](frontend/README.md) — env vars and scripts.
- [API schema (source-aligned)](docs/API_SCHEMA.md)
- [Environment variables](docs/ENVIRONMENT.md)

## Reference projects in this repo

- `Phase_2_PDZ_002_Model_Deploy` — SageMaker container / `server.py` / `test_sagemaker_endpoint.py`
- `Phase_2_PDZ_003_Test_Qdrant_Cloud` — Qdrant Cloud + ColQwen multivec patterns
