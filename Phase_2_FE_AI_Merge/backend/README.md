# Phase 2 FE AI Merge — Backend

## Architecture

```
app/
  api/routes/          # FastAPI routers (thin)
  services/            # Business logic: indexing, search, processing, insights
  repositories/        # Qdrant clients, BM25 persistence
  core/paths.py        # Paths + YAML merge with env
agent/                 # Chat runtime adapters (local Strands vs Bedrock AgentCore runtime)
src/                   # Legacy pipeline: processor, chunking, retrieval helpers, generation
config/default.yaml    # Pipeline + Qdrant + inference settings
```

- **Dense text retrieval** uses **Qdrant** (cosine on `sentence-transformers` embeddings) in one shared text collection, tenant-scoped by payload `user_id`.
- **BM25** uses per-user sidecar files: local mode `backend/output/retrieval/*`; S3 mode `s3://<processed-bucket>/<user-prefix>/retrieval/{bm25_index.pkl,documents.json.pkl}`.
- **Hybrid** fuses BM25 + dense (Qdrant) with weight `inference.hybrid_alpha` (default 0.5).
- **Image retrieval** stores **ColQwen multivectors** in one shared image collection, tenant-scoped by payload `user_id` (MaxSim).

### File storage (local vs S3)

Set `FILE_STORAGE_BACKEND` in `.env` (see `.env.example`).

- **Local** — `backend/input` and `backend/output` are created and used end-to-end.
- **S3** — uploads and published artifacts live in **S3**; the pipeline syncs to a **per-user directory under the system temp folder** for Docling/pdf2image/ColQwen. Logs may show those temp paths even when citations show `s3://...` (pdf2image reads local files; S3 is the durable object store).

Per-user isolation: HTTP header **`X-User-Id`**. S3 keys default to `users/<id>/...` under your configured prefixes (`S3_USER_ISOLATION=true`).

## Install dependencies (recommended: `backend/.venv`)

From this backend folder:

```powershell
Set-Location "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you already use a root venv at `Code/.venv`, activate it first, then install with `python -m pip install -r requirements.txt`.

Always prefer **`python -m pip`** for the exact venv you intend to use.

## Run locally

```powershell
Set-Location "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\backend"
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
# Fill keys and runtime variables before first run.
python run_api.py
```

Or without activating, run the API with the full interpreter:

```powershell
& ".\.venv\Scripts\python.exe" run_api.py
```

```bash
cd backend
cp .env.example .env
# fill OPENAI_API_KEY, Qdrant, and optional SageMaker / Bedrock values
```

Open `http://localhost:5000/docs` for OpenAPI.

## HTTP API reference

All **`/api/*`** routes (except where noted) respect the storage user from header **`X-User-Id`** (optional; sanitized; default from **`DEFAULT_STORAGE_USER_ID`** / `default`). Use the **same** user for upload → process → index → search → files → insights.

### Health, config, status

| Method | Path | Query / notes |
|--------|------|----------------|
| GET | `/health`, `/api/health` | Liveness. |
| GET | `/api` | Service name, version, link to `/docs`. |
| GET | `/api/config` | Merged YAML + env runtime settings. |
| GET | `/api/system/inference` | SageMaker flag, endpoint, region, Qdrant mode, collection names. |
| GET | `/api/status` | Pipeline/index summary: `ready`, `indexed_docs`, `image_pages`, nested `text_index` / `image_index` (Qdrant point counts, retriever metadata). **Caching:** responses are cached in-process per user for **`STATUS_QDRANT_CACHE_TTL_SECONDS`** (default **20**; set **0** to disable). **`fresh=true`:** bypass cache (use after **`POST /api/process`** or **`POST /api/index`**). |

### Files and processed tree

| Method | Path | Query / body | Response / notes |
|--------|------|--------------|------------------|
| GET | `/api/files` | **`quick`** (bool): if `true`, only lists **input/**; skips processed scan, `documents.json`, and Qdrant image count (faster right after upload). | `{ "input": [...], "processed": [...], "indexed": [...] }` — flat rows with paths, sizes, stages where applicable. |
| GET | `/api/files-with-metadata` | - | Enriched input rows with `status`, `processed_*`, and index detail fields: `indexed_text`, `indexed_image`, `index_status` (`none` \| `text` \| `image` \| `all`). |
| GET | `/api/file-metadata/{file_name}` | URL-encoded file name | Returns sidecar metadata (local or S3), plus processed mapping (`processed_document_id`, `processed_display_name`, `processed_safe_name`). |
| GET | `/api/processed-documents` | **`preview`** (bool): if `true`, embed short text snippets for `.md` / `.json` / `.txt` (slower on large trees). | Snapshot: **`input_file_count`**, **`artifact_count`**, **`document_count`** (sidebar rows including pipeline-wide group), **`named_document_folders`** (stage3/4 document folders only), **`stage_order`**, **`stage_totals`**, **`root_files`**, **`documents`** (each with `id`, `display_name`, `total_files`, **`stages`** map per pipeline stage with `file_count` + `files` rows), **`count_hints`**. Each file row includes **`relative_path`** (posix, under `processing/`), **`name`**, **`size`**, **`size_bytes`**, **`modified`**, **`type`**, **`storage`**. |
| GET | `/api/processed-file` | **`rel_path`** (required): path under **`processing/`** using forward slashes, e.g. `stage3_document_processed/MyDoc/MyDoc.md` or `.processing_cache.json`. No `..` or empty segments. | Raw bytes, **`Content-Type`** from file or object metadata, **`Content-Disposition: inline`**. **403** if path escapes processing tree or S3 key outside prefix; **404** missing; **413** if larger than **`MAX_PROCESSED_FILE_PREVIEW_BYTES`** (default 50MB). |
| POST | `/api/upload` | `multipart/form-data`, field **`files`** (repeatable). | `{ "uploaded", "count", "files" }`. |
| DELETE | `/api/files` | JSON **`{ "path": "<storage-relative or absolute path as returned by API>" }`**. | `{ "deleted": path }` or 404. |

### Chat assistant and chat history

| Method | Path | Query / body | Response / notes |
|--------|------|--------------|------------------|
| POST | `/api/chat/stream` | Body: `query`, optional `session_id`, optional `persona`, optional `education_description`. | SSE stream with `session`, `status`, `tool_trace`, `token`, `suggestions`, `done`. Persists messages when history is enabled/configured. |
| GET | `/api/chat/sessions` | Query: `limit`, `cursor`. | Paged session list for current user. |
| POST | `/api/chat/sessions` | Body: optional `session_id`, optional `title`, optional `pinned`. | Creates/ensures a chat session. |
| PATCH | `/api/chat/sessions/{session_id}` | Body: `title` and/or `pinned`. | Rename and pin/unpin session metadata. |
| DELETE | `/api/chat/sessions/{session_id}` | - | Deletes one session and all its messages. |
| GET | `/api/chat/sessions/{session_id}/messages` | Query: `limit`, `cursor`, `newest_first`. | Paged message history for a session. |

### Pipeline, search, images

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/processing-stats` | Reads pipeline stats JSON when present. |
| POST | `/api/process` | Query **`force`**. Body supports `selected_paths` and `mode` (`standard` \| `fast`). Fast mode simplifies Docling/ASR settings for speed. |
| POST | `/api/index` | Query **`force`**. Body supports `selected_paths`, `selected_names`, and `mode` (`standard` \| `fast`). Fast mode performs **text index only**. |
| POST | `/api/index/text`, `/api/index/image` | Partial index builds. |
| POST | `/api/search` | Body: **`query`**, **`top_k`**, **`retriever_type`** (`bm25` \| `dense` \| `hybrid`), **`include_images`**, **`images_for_generation`**. |
| GET | `/api/image`, `/api/pdf-page-image` | Media helpers (path / PDF page rendering). |

### Insights (`/api/insights`)

These routes build LLM context from **processed pipeline markdown** (`processing/stage3_document_processed/**/*.md`, falling back to `stage4_rag_ready` if stage3 has no `.md` for the scope). They do **not** query Qdrant or run hybrid retrieval.

| Method | Path | Body highlights |
|--------|------|-----------------|
| POST | `/api/insights/summary` | Optional **`document_id`** (folder name only). **`focus_query`** steers emphasis only. **`depth`**, **`tone`**, **`target_length`**. **`top_k`** is ignored (kept for API compatibility). |
| POST | `/api/insights/mcq` | **`topic`**, **`num_questions`**, **`difficulty`**, optional **`document_id`**. **`question_style`**, **`include_explanations`**. |
| POST | `/api/insights/learning-roadmap` | **`goals`** (required), optional **`student_profile`**, optional **`document_id`**. |
| GET | `/api/insights/analytics` | Placeholder / FR-020. |

OpenAPI at **`/docs`** remains authoritative for exact schemas and trying requests.

## Admin observability and usage telemetry (April 2026)

The admin dashboard and invocation explorer are backed by DynamoDB usage telemetry.

### Admin APIs

| Method | Path | Query / notes |
|--------|------|----------------|
| GET | `/api/admin/dashboard` | Query: `days` (1..365). Returns summary cards and day/hour trend series used by admin charts. |
| GET | `/api/admin/invocations` | Query: `days`, `user_id`, `feature`, `model_id`, `limit` (1..5000). Returns invocation rows for admin filtering. |

If `DYNAMODB_APP_USAGE_TABLE` is not configured, these endpoints return safe empty payloads instead of failing.

### Telemetry write rules

- A usage row is persisted only when request header `X-User-Id` is present and valid (non-empty, non-default placeholder).
- Requests without a valid user id are skipped for usage telemetry.
- CORS preflight (`OPTIONS`) traffic is not persisted as usage telemetry.
- Numeric values are normalized for DynamoDB (`float` to `Decimal`) before write.
- Background persistence is async-safe; failures are caught and logged so API responses are not broken.

## Unit tests

Tests live under `tests/` (`api/` for route smoke tests with mocks, `services/` for core settings, Qdrant factory, ColQwen inference flags). Run from **`backend`** using the same active venv you used for install.

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
python -m pytest tests\ -v
```

Optional: `pytest -m unit` (markers in `pytest.ini`). Pass extra pytest args to the scripts, e.g. `.\run_tests.ps1 tests\services -q`.

## Related Maintained Docs

- [`../../docs/technical/APPLICATION_OVERVIEW.md`](../../docs/technical/APPLICATION_OVERVIEW.md) — maintained application overview and architecture summary.
- [`../../docs/technical/API_REFERENCE.md`](../../docs/technical/API_REFERENCE.md) — reviewer-level API map.
- [`../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) — performance evidence and scaling plan.
- [`../terraform/README.md`](../terraform/README.md) — AWS infrastructure for the maintained merged application.

## Indexing workflow

Use the same **`X-User-Id`** (if any) for upload → process → index → search.

1. `POST /api/upload` — **local:** `backend/input/` · **S3:** object in originals bucket (+ sync to temp input on process).
2. `POST /api/process` — normalization → **local:** `backend/output/processing/...` · **S3:** temp workspace then `publish` to processed bucket.
3. `POST /api/index` (or text + image separately) — upserts tenant-filtered points into shared Qdrant collections and writes per-user BM25 sidecars. With S3, chunk/image metadata gets **`storage_uri`** for UI citations (re-run index after changing storage or paths).

See `docs/QDRANT_MULTITENANCY.md` for the multitenancy standard and migration notes.

## Fast vs Standard modes

### Processing mode (`POST /api/process`)

- **`standard`** (default): full quality pipeline (VLM, images/tables export, base ASR by config).
- **`fast`**: speed-oriented profile:
  - disable VLM image descriptions
  - disable extracted image/table export
  - use Whisper `tiny`
  - disable word timestamps
  - increase frame interval (fewer video frames)

Example body:

```json
{
  "selected_paths": ["s3://your-originals/users/u1/input/file.pdf"],
  "mode": "fast"
}
```

### Indexing mode (`POST /api/index`)

- **`standard`** (default): text + image indexing.
- **`fast`**: text-only indexing (image index skipped intentionally).

Example body:

```json
{
  "selected_paths": ["s3://your-originals/users/u1/input/file.pdf"],
  "selected_names": ["file.pdf"],
  "mode": "fast"
}
```

## Search / generation and “local rendering”

`/api/search` loads text models and (if enabled) **ColQwen** on the API host, queries **Qdrant Cloud** (or self-hosted), and may call **pdf2image** on **local paths** under the user workspace to build images for the vision LLM. That does **not** mean PDFs are “processed only locally forever” — S3 holds the published PDFs; the temp copy is what Poppler and the generator open.

## Inference: local vs SageMaker

Set in **environment** (recommended) or `config/default.yaml` under `inference`:

| Variable | Meaning |
|----------|---------|
| `USE_AWS_SAGEMAKER_INFERENCE=true` | Use **SageMaker Runtime** for ColQwen `embed-query` / `embed-images` (JSON contract matches `Phase_2_PDZ_002_Model_Deploy/server.py`). |
| `AWS_REGION` | e.g. `us-west-2` |
| `SAGEMAKER_ENDPOINT_NAME` | e.g. `phase2-colqwen-rt` |

When `false`, ColQwen loads locally (GPU/CPU) via `colpali-engine`.

Probe: `GET /api/system/inference`.

## Chat runtime mode switch (local vs AgentCore)

Use these backend env vars to control chat runtime mode:

| Variable | Meaning |
|----------|---------|
| `CHAT_AGENT_RUNTIME` | `local` (default) or `agentcore-runtime`. |
| `AGENTCORE_RUNTIME_ARN` | Required when `CHAT_AGENT_RUNTIME=agentcore-runtime`; deployed Bedrock AgentCore runtime ARN. |
| `AGENTCORE_REGION` | Region for AgentCore memory/runtime calls (example: `us-west-2`). |
| `AGENTCORE_MEMORY_ID` | Optional memory id for local Strands + AgentCore memory integration. |
| `DYNAMODB_CHATBOT_SESSIONS_TABLE` | Chat session table name (default `chatbot-session`). |
| `DYNAMODB_CHATBOT_MESSAGES_TABLE` | Chat message table name (default `chatbot-messages`). |

AgentCore runtime packaging helpers are in `backend/agent/`:

- `agentcore_runtime_entrypoint.py`
- `requirements-agentcore-runtime.txt`

For full details (API contract, PK/SK schema, frontend behavior), see [`docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md`](docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md).

## Run locally
pip install -r requirements.txt
python run_api.py       # Main entrypoint

## Docker

```bash
docker build -t phase2-ai-backend .
docker run -p 5000:5000 --env-file .env phase2-ai-backend
```
