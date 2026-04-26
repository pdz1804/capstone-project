# Phase 2 — AI Service (refactored)

This folder is the **refactored Phase 2** deliverable: a **layered backend** (API → Service → Repository → Qdrant + files), **Qdrant** as the vector database (no on-disk FAISS for dense text), **configurable ColQwen inference** (local GPU vs **AWS SageMaker** endpoint), optional **S3-backed file storage** with **per-user prefixes**, and a **React** UI.

For maintained infrastructure-as-code, use `Phase_2_FE_AI_Merge/terraform`. This folder is retained as an AI-service reference and is not the primary deployment tree.

## Layout


| Path        | Role                                                                               |
| ----------- | ---------------------------------------------------------------------------------- |
| `backend/`  | FastAPI app (`app/`), legacy `src/` processors & generators, `config/default.yaml` |
| `frontend/` | Vite + React client (proxies `/api` to port 8000)                                  |
| `docs/`     | API schema, environment reference, storage notes                                   |


## Quick start

1. **Qdrant** — Docker locally or **Qdrant Cloud** (`QDRANT_MODE=cloud`, URL + API key). See `docs/ENVIRONMENT.md` and `Phase_2_PDZ_003_Test_Qdrant_Cloud`.
2. **Backend** — `cd backend`, venv, `pip install -r requirements.txt`, copy `.env.example` → `.env`, then `python run_api.py` (or `uvicorn app.main:app --reload --port 8000`).
3. **Frontend** — `cd frontend`, `npm install`, `npm run dev`.

## Storage: local disk vs Amazon S3


| Mode                | Env                          | Where uploads live                                                           | Where pipeline runs                                                                                          |
| ------------------- | ---------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Local** (default) | `FILE_STORAGE_BACKEND=local` | `backend/input/`                                                             | `backend/output/` (processing + retrieval)                                                                   |
| **S3**              | `FILE_STORAGE_BACKEND=s3`    | **S3 originals bucket** (plus optional `S3_INPUT_PREFIX` + per-user segment) | **Ephemeral directory** under OS temp: `%TEMP%\phase2_ai_workspace\<user>\...` — **not** next to source code |


With S3:

- `**prepare_pipeline_input`** downloads objects from the originals bucket into the user’s temp `input/`.
- **Docling / normalizers / media** run on that local tree (libraries require real paths).
- `**publish_pipeline_output`** uploads the `processing/` tree to the **processed** bucket.

So **authoritative blobs are on S3**; the temp folder is a **sync + compute cache** for one machine.

### Multi-user API convention

Send header `**X-User-Id`** (sanitized: letters, digits, `.`, `_`, `-`) on upload, process, index, search, status, files, insights, and image routes. If omitted, `**DEFAULT_STORAGE_USER_ID**` or `default` is used.

With S3, keys are normally under `**users/<id>/**` after your bucket prefixes (`S3_USER_ISOLATION=true`, default). Set `S3_USER_ISOLATION=false` only for a single shared prefix (legacy/smoke tests).

Optional **vector isolation**: `QDRANT_ISOLATE_BY_USER=true` suffixes collection names per user (default is off — one shared `edu_text_chunks` / `edu_image_pages` unless you enable this).

More detail: `docs/STORAGE_ARCHITECTURE.md` and `backend/.env.example`.

## Why logs still show `C:\...\AppData\Local\Temp\...` with S3

That is **expected**.

- **Citations in the UI** show `**s3://...`** via `metadata.storage_uri` / image payload `storage_uri` after you re-index (`POST /api/index`) with S3 enabled.
- **Generation and pdf2image** still call **Poppler / Pillow / pdf2image** on a **file path**. Those tools do not read `s3://` directly. The app uses the **local copy** that was synced from S3 during `process` (same path layout as under `processing/stage4_rag_ready/...`).
- Logs therefore mention the **local workspace path** for rendering; they should also mention the **canonical S3 URI** where implemented (see `RAGGenerator` image logs).

ColQwen and sentence-transformers similarly run **on the API host** (or SageMaker for ColQwen if configured) — they are not “rendering inside S3.”

## Citations (text + vision)

After indexing with `FILE_STORAGE_BACKEND=s3`, chunk metadata and image Qdrant payloads include `**storage_uri`** (e.g. `s3://ai-service-processed-dev/users/default/stage4_rag_ready/...`). The UI prefers that for “S3 object” lines; `**source_path**` may remain the local path for server-side PDF page rendering.

## Newer UI and API features (refactor)

These sit on top of the core upload → process → index → search flow:


| Area                    | What it does                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Processed workspace** | `**GET /api/processed-documents`** returns one structured snapshot: input count, per-document stage folders (1→4), root-level files, and a **“Pipeline-wide · metadata & stats”** group for shared JSON/stats. Counts include `**document_count`**, `**named_document_folders**`, `**stage_totals**`, and human-readable `**count_hints**` (stage totals vs input files, what “document groups” mean). |
| **Legacy fallback**     | If the snapshot is empty or fails, the React app rebuilds the tree from flat `**GET /api/files`** `processed` rows and shows an amber notice.                                                                                                                                                                                                                                                          |
| **File preview**        | `**GET /api/processed-file?rel_path=…`** streams a single file under `processing/` (local or S3), path-safe, max size `**MAX_PROCESSED_FILE_PREVIEW_BYTES**` (default 50MB). The UI opens `**ProcessedFilePreviewModal**` (markdown, JSON, text, PDF, images, video, or download for binary).                                                                                                          |
| **Status + Qdrant**     | `**GET /api/status`** still returns index readiness and Qdrant point counts, but the server **caches** results per user (`**STATUS_QDRANT_CACHE_TTL_SECONDS`**, default 20s; `0` disables). Use `**?fresh=true**` after process/index when you need up-to-date counts. The UI polls on a longer interval and passes `**fresh**` only after user actions or manual refresh.                             |
| **Insights**            | Summary, MCQ, and roadmap use **processed `.md`** from **`stage3_document_processed`** (then stage4 if needed), not vector search. Optional **`document_id`** scopes to that folder name. Summary **`focus_query`** only steers the LLM; **`top_k`** is ignored. **`tone`**, **`target_length`**, MCQ **`question_style`** / **`include_explanations`** unchanged.                                        |


**Full method-by-method API tables:** [backend/README.md](backend/README.md#http-api-reference) and [docs/API_SCHEMA.md](docs/API_SCHEMA.md).

## Documentation

- [Backend README](backend/README.md) — architecture, indexing, inference, storage, **HTTP API reference**.
- [Frontend README](frontend/README.md) — env vars and scripts.
- [API schema](docs/API_SCHEMA.md)
- [Environment variables](docs/ENVIRONMENT.md)

## Reference projects in this repo

- `Phase_2_PDZ_002_Model_Deploy` — SageMaker container / `server.py` / `test_sagemaker_endpoint.py`
- `Phase_2_PDZ_003_Test_Qdrant_Cloud` — Qdrant Cloud + ColQwen multivec patterns

