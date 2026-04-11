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
