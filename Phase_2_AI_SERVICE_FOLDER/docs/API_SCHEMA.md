# API schema (aligned with `backend/app`)

All routes are served by FastAPI; **authoritative schemas** are in code (`backend/app/api/schemas.py`) and **OpenAPI** at `/docs` when the server runs.

Base path: **`/api`** for most resources (health also at `/health`).

**Multi-tenant storage:** send **`X-User-Id`** on upload, process, index, search, status, files, processed routes, and insights (optional; default user if omitted). See `docs/STORAGE_ARCHITECTURE.md` and `backend/.env.example`.

## Health & status

| Method | Path | Response (summary) |
|--------|------|---------------------|
| GET | `/health`, `/api/health` | `{ "status": "healthy", "timestamp": ISO8601 }` |
| GET | `/api/status` | `{ "ready", "indexed_docs", "image_pages", "text_index", "image_index" }`   text/image blocks include Qdrant point counts and retriever metadata. **Query:** **`fresh`** (bool, default `false`)   if `true`, skip server-side cache and re-query Qdrant. **Env:** **`STATUS_QDRANT_CACHE_TTL_SECONDS`** (default `20`, `0` = no cache). |
| GET | `/api/config` | YAML merged with env + `key_settings` |
| GET | `/api/system/inference` | `{ "use_aws_sagemaker_inference", "sagemaker_endpoint_name", "aws_region", "qdrant_mode", "text_collection", "image_collection" }` |

## Files & processed workspace

| Method | Path | Query | Notes |
|--------|------|-------|--------|
| GET | `/api/files` | **`quick`** (bool) | `{ "input", "processed", "indexed" }`. If **`quick=true`**, only **`input`** is populated (fast refresh after upload). |
| GET | `/api/processed-documents` | **`preview`** (bool) | Single-call tree for the Processed UI: **`documents`** (per-doc **`stages`** with **`files`** rows), **`root_files`**, **`stage_totals`**, **`document_count`**, **`named_document_folders`**, **`count_hints`**, etc. If **`preview=true`**, rows may include a short **`preview`** string for `.md`/`.json`/`.txt`. |
| GET | `/api/processed-file` | **`rel_path`** (string, required) | Raw file bytes under **`processing/`** (local or S3). Tenant-safe path (no `..`). **413** if over **`MAX_PROCESSED_FILE_PREVIEW_BYTES`** (default 50MB). Each file row from **`processed-documents`** includes **`relative_path`** for this query. |
| POST | `/api/upload` | `multipart/form-data` `files[]` | Saves to input (local or S3). |
| DELETE | `/api/files` | JSON `{ "path": "<path>" }` | Deletes by storage path as returned by list/upload APIs. |

### `GET /api/processed-documents` response shape (summary)

- **`input_file_count`**, **`artifact_count`**, **`document_count`**, **`named_document_folders`**
- **`stage_order`**: fixed pipeline stage keys
- **`stage_totals`**: file counts per stage (all artifacts in that folder)
- **`root_files`**: files not under a document bucket (e.g. top-level JSON)
- **`documents`**: array of groups; each has **`id`**, **`display_name`**, **`total_files`**, **`stages`**: for each stage, `{ "file_count", "files": [ { "name", "relative_path", "path", "size", "size_bytes", "modified", "type", "storage", "preview"? } ] }`
- One synthetic group may appear: **“Pipeline-wide · metadata & stats”** (`id` `__pipeline_shared__`) for shared pipeline artifacts
- **`count_hints`**: short strings explaining counts for the UI

## Pipeline

| Method | Path | Query | Notes |
|--------|------|-------|--------|
| GET | `/api/processing-stats` |   | Reads `output/processing/pipeline_stats.json` if present |
| POST | `/api/process` | `force` bool | Runs `DocumentProcessingPipeline` |
| POST | `/api/index` | `force` bool | Text + image Qdrant index |
| POST | `/api/index/text` | `force` bool | Text chunks → Qdrant + `documents.json` + BM25 pickle |
| POST | `/api/index/image` | `force` bool | PDF pages → ColQwen → Qdrant multivec |

## Search

| Method | Path | Body (JSON) |
|--------|------|-------------|
| POST | `/api/search` | `SearchRequest`: `query` (string, required), `top_k` (1–100, default 10), `retriever_type` (`bm25` \| `dense` \| `hybrid`), `include_images` (bool), `images_for_generation` (0–20) |

**Response:** `{ "query", "text_results", "image_results", "answer", "contents"? }`   same general shape as legacy Phase 2 (`contents` when generation succeeds).

## Images (media)

| Method | Path | Query |
|--------|------|-------|
| GET | `/api/image` | `path`   local file path |
| GET | `/api/pdf-page-image` | `pdf_name`, `page` (1-based) |

## Insights (SRS-style)

Context for summary / MCQ / roadmap is read from **processed pipeline markdown** (`stage3_document_processed/**/*.md`, then `stage4_rag_ready` if stage3 has no `.md` for that scope). **No Qdrant or hybrid search** is used for these endpoints.

| Method | Path | Body |
|--------|------|------|
| POST | `/api/insights/summary` | `focus_query?` (themes for the LLM only), `depth?`, `top_k?` (ignored), **`document_id?`** (folder name under stage3/4), **`tone?`**, **`target_length?`** |
| POST | `/api/insights/mcq` | `topic`, `num_questions`, `difficulty`, **`document_id?`**, **`question_style?`**, **`include_explanations?`** |
| POST | `/api/insights/learning-roadmap` | `student_profile?`, `goals`, **`document_id?`** |
| GET | `/api/insights/analytics` | Placeholder for FR-020 (no session store yet) |

## JSON examples

### Search

```json
{
  "query": "What is hybrid retrieval?",
  "top_k": 10,
  "retriever_type": "hybrid",
  "include_images": true,
  "images_for_generation": 5
}
```

### Summary

```json
{
  "focus_query": "week 3 lecture objectives",
  "depth": "detailed",
  "top_k": 12,
  "document_id": "My Lecture Folder",
  "tone": "friendly",
  "target_length": "medium"
}
```

### Processed file fetch (conceptual)

`GET /api/processed-file?rel_path=stage4_rag_ready/MyDoc/MyDoc.md`  
Headers: `X-User-Id: your-user` (if not default)
