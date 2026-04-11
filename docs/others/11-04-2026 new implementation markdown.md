# 11/04/2026 New Implementation Markdown

This document is the running implementation log for new enhancements.

Update rule:
- Every new implementation must be appended to this file with date, scope, files changed, and validation notes.

## 2026-04-11 - Knowledge Explorer Enhancements (Phase_2_FE_AI_Merge)

### Scope
- Improve citation behavior in generated answers so citations are placed at end of supporting sentences.
- Improve media transcript chunk rendering by allowing playback from the original media source at chunk timestamp.
- Ensure Retrieval-only mode still shows retrieved chunks (not only timing).
- Preserve/compute telemetry retrieval total for accurate wall-clock display.

### Implemented
1. Citation prompt updated for sentence-level citation placement.
- Added explicit rules and good/bad examples in generation prompt.
- File: `Phase_2_FE_AI_Merge/backend/src/generation/generator.py`

2. Media-original rendering support metadata.
- During metadata enrichment, media chunks now keep `original_storage_uri` when resolvable from original input file.
- API metadata sanitizer now keeps `preview_source_path` fallback while stripping raw `original_file` key when `storage_uri` is present.
- File: `Phase_2_FE_AI_Merge/backend/app/services/citation_uris.py`

3. Local preview source security + scope expanded.
- `/api/search/image-preview` now accepts local source paths under processing and input roots (for local backend media playback).
- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

4. Retrieval-only chunk rendering on frontend.
- Search page now builds citation/chunk cards from `text_results` + `image_results` when `contents` is absent.
- File: `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

5. Media chunk playback in Knowledge Explorer.
- For text citations with `document_type=media`, UI can load original media source.
- Renders `<video>`/`<audio>` and seeks to chunk `start_time` on metadata load.
- File: `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

6. Accurate retrieval telemetry rendering.
- Frontend uses `retrieval_total` when available, with fallback for older responses.
- File: `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

### Related previously-implemented optimization context (same date)
- Text/image branch parallel retrieval wall-clock telemetry added.
- Hybrid BM25+dense retrieval parallelization.
- Embedder/model caching for reduced repeated cold loads.
- Generation image preparation parallelization.

### Validation
- Frontend build passed (`vite build`).
- Modified backend modules pass Python syntax compile (`py -3 -m py_compile ...`).
- Note: Full pytest execution in current terminal was blocked by environment interpreter mismatch.

### Operational note
- To fully benefit from `original_storage_uri` for already-indexed media chunks, re-index documents so stored metadata includes this new field.

## 2026-04-11 - Retrieval-only Label Normalization (Knowledge Explorer)

### Scope
- Fix Retrieval-only chunk card title to avoid full file paths.

### Implemented
1. Retrieval-only chunk labels now prefer `metadata.doc_id`.
2. Fallback label uses sanitized basename (without extension) from `filename/source/storage_uri/source_path`.
3. Citation header rendering updated to use normalized display names for both text and image rows.

### Files changed
- `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

### Validation
- Frontend static diagnostics report no errors for updated file.

## 2026-04-11 - Deployed Media Preview Hardening

### Scope
- Ensure media preview works reliably in deployed environments even for previously indexed chunks.

### Implemented
1. Retrieval-time backfill of `original_storage_uri` for media chunks:
	- In text retrieval service, media metadata now attempts to infer original media S3 URI from `original_file`/`preview_source_path` using current tenant storage mapping.
	- This enables playback in deployment without requiring immediate full re-index for every historical chunk.

2. UI guard against non-media fallback URIs:
	- Media playback now prefers `original_storage_uri`.
	- Fallback to `storage_uri` only if it looks like an actual media file path.
	- If no valid source is available, UI shows a clear message instead of attempting broken preview.

### Files changed
- `Phase_2_FE_AI_Merge/backend/app/services/text_search_service.py`
- `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

### Validation
- Frontend build passed (`vite build`).
- Backend syntax compile passed for modified module.

## 2026-04-11 - BM25 Media URI Resolution For Deployment

### Issue observed
- Retrieval-only media preview URL sometimes used `source_path=C:\...\input\*.mp4` on deployed domain, indicating missing/failed S3 URI hydration for some BM25 snapshot rows.

### Root cause
- BM25 documents are read from persisted `retrieval/documents` snapshot.
- Older rows may contain machine-local `original_file`/`preview_source_path` paths that cannot be directly mapped to current runtime local roots.
- In that case `original_storage_uri` was empty, and UI fell back to `source_path`.

### Implemented
1. Backend media URI fallback synthesis:
	- If direct local->S3 mapping fails, infer original media URI using filename basename (or `doc_id` + `original_file_format`) under tenant input prefix.
	- File: `Phase_2_FE_AI_Merge/backend/app/services/text_search_service.py`

2. Frontend deployed guard:
	- For media preview, only allow `source_path` fallback on localhost.
	- On deployed hosts, rely on `storage_uri`/`original_storage_uri` only.
	- File: `Phase_2_FE_AI_Merge/frontend/src/views/SearchView.tsx`

## 2026-04-11 - S3 NoSuchKey Fix For Media Preview

### Issue observed
- Preview endpoint received storage URI key like:
  - `s3://.../users/<id>/C:/Users/.../05_NLP_Basic_4.mp4`
- This caused S3 `NoSuchKey` and a 500 response.

### Root cause
- Runtime in Linux parsed Windows absolute path using `Path(...).name`, which kept the full `C:\...` string instead of basename.
- That value was appended to tenant S3 prefix, producing an invalid object key.

### Implemented
1. Cross-platform basename extraction for URI synthesis:
	- Added OS-agnostic basename helper that normalizes both `\\` and `/` separators.
	- Media URI synthesis now uses basename only (e.g. `05_NLP_Basic_4.mp4`).
	- File: `Phase_2_FE_AI_Merge/backend/app/services/text_search_service.py`

2. Safer preview API error behavior:
	- `/api/search/image-preview` now catches S3 `NoSuchKey` and returns HTTP 404 instead of 500.
	- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

## 2026-04-11 - Redis Query Result Cache (10-minute TTL)

### Scope
- Cache `/api/search` response payloads for identical query requests.
- Use production-grade cache client library (`redis-py`) with env toggles.
- Support both local Docker Redis and AWS ElastiCache Redis.

### Implemented
1. Redis cache client service:
	- Added `SearchCacheClient` with deterministic key hashing by `user_id + full search request payload`.
	- Supports configurable TTL (default 600 seconds = 10 minutes).
	- Fails open: if Redis unavailable, search still executes normally.
	- File: `Phase_2_FE_AI_Merge/backend/app/services/search_cache.py`

2. Search route integration:
	- `/api/search` now checks cache before invoking orchestrator.
	- On miss, executes search and writes result to cache.
	- Response includes cache metadata (`enabled`, `hit`, `backend`, `ttl_seconds`).
	- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

3. Environment configuration:
	- Added cache env vars to backend `.env` with 10-minute default TTL.
	- File: `Phase_2_FE_AI_Merge/backend/.env`

4. Dependency update:
	- Added `redis>=5.0.0` to backend requirements.
	- File: `Phase_2_FE_AI_Merge/backend/requirements.txt`

5. Setup guide for local Docker + ElastiCache:
	- Added operational doc with exact values and commands.
	- File: `docs/others/search-cache-redis-setup.md`

6. Tests:
	- Added route-level cache hit/miss unit tests.
	- File: `Phase_2_FE_AI_Merge/backend/tests/api/test_search_cache.py`

### Validation
- Python syntax compile passed for updated modules.
- API tests passed:
	- `tests/api/test_routes_with_mocks.py`
	- `tests/api/test_search_cache.py`

## 2026-04-11 - ElastiCache Endpoint Switch Guidance In .env

### Scope
- Add explicit environment comments for switching Redis cache endpoint between local Docker and AWS ElastiCache.

### Implemented
1. Added deployment switch comments in backend `.env` under Search Result Cache section:
	- Included exact endpoint example:
	  - `redis://rag-pipeline-cache-jx9fd6.serverless.usw2.cache.amazonaws.com:6379/0`
	- Included TLS variant guidance using `rediss://`.

### Files changed
- `Phase_2_FE_AI_Merge/backend/.env`

### Validation
- Manual `.env` review confirms local default remains `redis://localhost:6379/0` and deployment alternative is documented inline.

## 2026-04-11 - Search Cache Observability Logs

### Scope
- Make cache behavior visible in runtime logs (client status, hit, miss, write success).

### Implemented
1. Added explicit cache client logs:
	- cache disabled status (env/backend)
	- cache connected
	- cache hit
	- cache miss
	- cache write success/failure
	- File: `Phase_2_FE_AI_Merge/backend/app/services/search_cache.py`

2. Added route-level cache decision logs:
	- cache-check status per `/api/search` request
	- served-from-cache log
	- miss-path completion log with `write_ok`
	- Response cache metadata now includes `write_ok`.
	- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

### Validation
- Python syntax compile passed for updated modules.
- Existing cache route tests continue to pass.

## 2026-04-11 - Shared Retrieval Cache Scope (Knowledge Explorer + Chat Assistant)

### Scope
- Move cache scope to retrieved contents in the shared orchestration layer so both Knowledge Explorer and Chat Assistant retrieval tools use the same cache entries.

### Implemented
1. Namespace-aware cache keys:
	- `SearchCacheClient` now supports cache namespaces (`search`, `retrieval`) in key construction.
	- Cache logs now include namespace to distinguish route-response cache vs retrieval-content cache events.
	- File: `Phase_2_FE_AI_Merge/backend/app/services/search_cache.py`

2. Orchestrator-level retrieval caching:
	- `SearchOrchestrator.run(...)` now performs cache `get`/`set` for retrieval results (`text_results`, `image_results`) using namespace `retrieval`.
	- Applies uniformly to both `/api/search` and chat tool calls (`text_rag`, `image_rag`) because both execute through the same orchestrator.
	- Added telemetry metadata under `telemetry.cache.retrieval` (`enabled`, `hit`, `backend`, `ttl_seconds`, `write_ok`).
	- File: `Phase_2_FE_AI_Merge/backend/app/services/search_orchestrator.py`

3. Unit tests for shared scope:
	- Added tests verifying retrieval cache reuse across separate orchestrator instances (simulating different API surfaces) and per-user isolation.
	- File: `Phase_2_FE_AI_Merge/backend/tests/services/test_orchestrator_retrieval_cache.py`

### Validation
- Added/updated unit tests for orchestrator retrieval cache behavior.

## 2026-04-11 - Retrieval-Only Cache Scope Correction + Timing Logs + Qdrant Call Reduction

### Scope
- Enforce cache scope to retrieved chunks only (not full `/api/search` response payloads).
- Print retrieval and generation times in logs.
- Reduce repeated Qdrant API calls during retrieval.

### Implemented
1. Removed route-level full-response cache from `/api/search`:
	- The route now always invokes `SearchOrchestrator` and no longer serves/stores whole API response objects from Redis.
	- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

2. Added explicit timing logs at route level:
	- Logs now print `retrieval_ms`, `generation_ms`, `total_ms`, and retrieval cache hit status for each `/api/search` call.
	- File: `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`

3. Added explicit timing logs inside orchestrator:
	- Logs now print retrieval/generation/total timings for all execution branches (`retrieval_only`, no-results, and full completion).
	- File: `Phase_2_FE_AI_Merge/backend/app/services/search_orchestrator.py`

4. Reduced repeated Qdrant collection/index ensure calls:
	- Text retrieval now prepares each text collection once per process before dense/hybrid queries.
	- Image retrieval now prepares each image collection once per process before search.
	- This removes repeated `get_collections` + `create_payload_index` traffic on every request.
	- Files:
	  - `Phase_2_FE_AI_Merge/backend/app/services/text_search_service.py`
	  - `Phase_2_FE_AI_Merge/backend/app/services/image_search_service.py`

5. Updated tests/docs to match corrected cache scope:
	- Updated route tests for no top-level route cache behavior.
	- Updated Redis setup doc to describe retrieval-content caching semantics.
	- Files:
	  - `Phase_2_FE_AI_Merge/backend/tests/api/test_search_cache.py`
	  - `docs/others/search-cache-redis-setup.md`

### Validation
- Targeted API + service cache tests pass in backend virtual environment.
