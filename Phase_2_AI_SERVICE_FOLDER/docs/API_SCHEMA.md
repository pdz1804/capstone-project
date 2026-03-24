# API schema (aligned with `backend/app`)

All routes are served by FastAPI; **authoritative schemas** are in code (`backend/app/api/schemas.py`) and **OpenAPI** at `/docs` when the server runs.

Base path: **`/api`** for most resources (health also at `/health`).

## Health & status

| Method | Path | Response (summary) |
|--------|------|---------------------|
| GET | `/health`, `/api/health` | `{ "status": "healthy", "timestamp": ISO8601 }` |
| GET | `/api/status` | `{ "ready", "indexed_docs", "image_pages", "text_index", "image_index" }` — text uses Qdrant + BM25 metadata |
| GET | `/api/config` | YAML merged with env + `key_settings` |
| GET | `/api/system/inference` | `{ "use_aws_sagemaker_inference", "sagemaker_endpoint_name", "aws_region", "qdrant_mode", "text_collection", "image_collection" }` |

## Files

| Method | Path | Body / query | Notes |
|--------|------|--------------|--------|
| GET | `/api/files` | — | `{ "input": [...], "processed": [...], "indexed": [...] }` |
| POST | `/api/upload` | `multipart/form-data` `files[]` | Saves under `backend/input/` |
| DELETE | `/api/files` | JSON `{ "path": "<absolute or project path>" }` | |

## Pipeline

| Method | Path | Query | Notes |
|--------|------|-------|--------|
| GET | `/api/processing-stats` | — | Reads `output/processing/pipeline_stats.json` if present |
| POST | `/api/process` | `force` bool | Runs `DocumentProcessingPipeline` |
| POST | `/api/index` | `force` bool | Text + image Qdrant index |
| POST | `/api/index/text` | `force` bool | Text chunks → Qdrant + `documents.json` + BM25 pickle |
| POST | `/api/index/image` | `force` bool | PDF pages → ColQwen → Qdrant multivec |

## Search

| Method | Path | Body (JSON) |
|--------|------|-------------|
| POST | `/api/search` | `SearchRequest`: `query` (string, required), `top_k` (1–100, default 10), `retriever_type` (`bm25` \| `dense` \| `hybrid`), `include_images` (bool), `images_for_generation` (0–20) |

**Response:** `{ "query", "text_results", "image_results", "answer", "contents"? }` — same general shape as legacy Phase 2 (`contents` when generation succeeds).

## Images (media)

| Method | Path | Query |
|--------|------|-------|
| GET | `/api/image` | `path` — local file path |
| GET | `/api/pdf-page-image` | `pdf_name`, `page` (1-based) |

## Insights (SRS-style)

| Method | Path | Body |
|--------|------|------|
| POST | `/api/insights/summary` | `{ "focus_query"?, "depth"?: brief\|detailed\|comprehensive, "top_k"?: int }` |
| POST | `/api/insights/mcq` | `{ "topic", "num_questions", "difficulty" }` |
| POST | `/api/insights/learning-roadmap` | `{ "student_profile"?, "goals" }` |
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
  "top_k": 12
}
```
