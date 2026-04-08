# Indexing Flow (Local vs Cloud)

This document explains how indexing is implemented (`POST /api/index`, `/api/index/text`, `/api/index/image`), where data goes, and how Local vs Cloud mode changes behavior.

It is based on current code in:
- `app/api/routes/pipeline_routes.py`
- `app/services/indexing_service.py`
- `app/services/document_chunks.py`
- `src/retrieval/rag_retrievers.py`
- `app/repositories/text_index_repository.py`
- `app/repositories/image_index_repository.py`
- `app/repositories/bm25_store.py`
- `app/repositories/qdrant_factory.py`
- `app/services/colqwen_inference.py`
- `app/services/citation_uris.py`
- `app/storage/service.py`

Scope boundary:
- All statements in this document are derived from `Phase_2_FE_AI_Merge/backend/*`.
- Any remote service mention (Qdrant Cloud/SageMaker) is described only via code paths and request contracts implemented in this folder.

---

## 1) Entry Points

### Main endpoints
- `POST /api/index` -> runs text + image indexing (or text-only in fast mode).
- `POST /api/index/text` -> text index only.
- `POST /api/index/image` -> image index only.

### Request controls
- `force`: recreate collections when needed.
- `selected_paths`: optional input paths/URIs to scope indexing.
- `selected_names`: optional filenames to help matching processed artifacts.
- `mode`:
  - `standard` -> text + image
  - `fast` -> text only

---

## 2) Storage and Vector Backend Modes

Indexing has two orthogonal dimensions:

1. File storage mode (`FILE_STORAGE_BACKEND`)
- local: workspace artifacts on local disk
- s3: canonical artifacts in S3 (with local temp workspace for processing/index runtime)

2. Qdrant mode (`QDRANT_MODE` / config)
- docker/local host mode (`host`, `port`)
- cloud mode (`url`, `api_key`)

So "cloud mode" in practice often means:
- `FILE_STORAGE_BACKEND=s3`
- `QDRANT_MODE=cloud`
- optionally SageMaker inference for ColQwen embeddings

---

## 3) Text Indexing Flow (Detailed)

## Step 1: Preconditions
- `IndexingService.index_text()` checks `stage4_rag_ready` exists.
- If missing: fails and asks to run processing first.
- In current implementation, indexing does not auto-download Stage 4 artifacts from S3. It uses the local workspace Stage 4 tree prepared by prior pipeline runs in this backend.

## Step 2: Load indexable documents/chunks
- `load_documents_for_indexing()` creates `RAGRetrieverManager`.
- `RAGRetrieverManager.load_documents()` reads Stage 4 folders:
  - Regular docs: reads `<doc>/<doc>.md`, then chunking is applied (if enabled).
  - Media docs (`media_manifest.json` + `transcript_chunks.json`): pre-built transcript chunks are loaded directly (no re-chunking).
  - Excel docs (`excel_manifest.json` + `excel_chunks.json`): pre-built Excel chunks are loaded directly.

Result:
- A unified list of chunk documents for indexing.

## Step 3: Optional selection filter
- If `selected_paths` or `selected_names` is provided, chunks are filtered by:
  - original filename
  - source path
  - chunk/document id
  - parent folder names

## Step 4: Storage URI enrichment (important for cloud citations)
- `enrich_chunk_documents_storage_uris()` runs before embedding.
- In S3 mode, it maps local temp paths to canonical `s3://...` URIs and stores them in chunk metadata.

## Step 5: Create text embeddings
- Uses `sentence-transformers` model from config (`text_retrieval.embedding_model`).
- Encodes all chunk texts into dense vectors.

## Step 6: Ensure Qdrant text collection
- `TextIndexRepository.ensure_collection()`:
  - creates collection if needed
  - sets cosine distance
  - creates payload indexes (`user_id`, `source`, `chunk_id`)
  - optional quantization config from YAML

## Step 7: Upsert chunk points
- `TextIndexRepository.upsert_chunks()` writes points to Qdrant.
- Payload per chunk includes:
  - `user_id` (tenant isolation)
  - `chunk_id`
  - `source`
  - `text_preview`
  - optional `storage_uri` and `storage_backend`

## Step 8: Save BM25 sidecars
- `save_documents_snapshot()` stores chunk snapshot.
- `save_bm25_index()` builds sparse BM25 index payload from the same chunks.

Where sidecars go:
- Local file storage mode:
  - local retrieval files under retrieval directory (documents snapshot is written in pickle format to the configured documents path, and BM25 to pickle path)
- S3 file storage mode:
  - `retrieval/documents.json.pkl`
  - `retrieval/bm25_index.pkl`
  - stored in processed S3 prefix via `S3FileStorage.write_processed_bytes()`

---

## 4) Image Indexing Flow (Detailed)

## Step 1: Preconditions
- `index_images()` checks `stage4_rag_ready` exists.
- Creates/ensures Qdrant image collection with multivector config (MAX_SIM comparator).

## Step 2: Resolve document folders
- Iterates over document folders in Stage 4.
- Applies optional filtering from `selected_paths` / `selected_names`.

## Step 3: Build page/image units for embedding

For each doc folder:

- If a PDF exists:
  - convert each PDF page to image using `pdf2image`.
  - each page becomes one logical image point.

- If no PDF:
  - collect image files directly from Stage 4 subtree
  - (docling images, page images, media frames, etc.)

Each point gets payload with:
- `user_id`
- `source` (doc folder name)
- `source_path`
- `page`, `total_pages`
- image dimensions
- in S3 mode: `storage_uri` when mappable

## Step 4: Generate ColQwen embeddings
- `ColQwenInferenceService.embed_images()`:
  - Local inference path: loads ColQwen model locally and embeds images.
  - SageMaker path (`USE_AWS_SAGEMAKER_INFERENCE=true`): calls endpoint with `operation=embed-images`.

Result:
- Multi-vector embedding per page/image.

## Step 5: Upsert to Qdrant image collection
- `ImageIndexRepository.upsert_pages()` writes multivector points.
- Collection uses:
  - vector name (default `colpali_multivec`)
  - distance DOT
  - multivector comparator MAX_SIM
  - payload indexes (`user_id`, `source`, `page`, `source_path`)

## Step 6: Write image sidecar metadata
- `_write_image_sidecar()` writes:
  - `image_retrieval/image_index_meta.json`
  - `image_retrieval/colqwen/colqwen_meta.json`
- Tracks number of indexed pages and retriever metadata.

---

## 5) Index-All Behavior

`index_all()` always runs text indexing first.

- `mode=standard`:
  - runs image indexing after text.

- `mode=fast`:
  - skips image indexing intentionally.
  - returns `"status": "skipped_fast_mode"` for image part.

---

## 6) Exactly Where Data Goes

## Text data destinations
- Dense vectors -> Qdrant text collection.
- Sparse/BM25 snapshot -> local retrieval files or S3 retrieval objects.

## Image data destinations
- ColQwen multivectors -> Qdrant image collection.
- Small local sidecar metadata -> image retrieval meta files in workspace.

## Canonical source URIs for citations
- Local mode: local file paths are used.
- S3 mode: metadata is enriched with canonical `s3://...` URIs for UI/citation use.

---

## 7) Local Mode (End-to-End Summary)

Typical setup:
- `FILE_STORAGE_BACKEND=local`
- `QDRANT_MODE=docker` (or local host)
- `USE_AWS_SAGEMAKER_INFERENCE=false`

Flow:
1. Read Stage 4 artifacts from local output tree.
2. Build text chunks and image pages.
3. Embed locally (SentenceTransformer + local ColQwen).
4. Upsert to local/self-hosted Qdrant.
5. Save BM25/doc snapshot to local retrieval folder.

---

## 8) Cloud Mode (End-to-End Summary)

Typical setup:
- `FILE_STORAGE_BACKEND=s3`
- `QDRANT_MODE=cloud`
- optional `USE_AWS_SAGEMAKER_INFERENCE=true`

Flow:
1. Read Stage 4 from user local temp workspace (produced by prior processing runs in this backend workspace).
2. Build text chunks and image pages.
3. Add canonical S3 URIs to chunk/image metadata where possible.
4. Embed:
   - text embeddings locally (SentenceTransformer),
   - image embeddings locally or via SageMaker (depending flags).
5. Upsert vectors into Qdrant Cloud collections.
6. Save BM25/doc snapshots to processed S3 retrieval objects.

---

## 9) Tenant Isolation and Filtering

- Qdrant collections are shared by modality, but every point includes `user_id`.
- Searches and deletes are filtered by `user_id`.
- S3 prefixes can be user-isolated (`users/{id}/...`) when `S3_USER_ISOLATION=true`.
- Selection scoping for indexing is best-effort matching using names/stems/source fields.

---

## 10) What Search Uses After Indexing

`/api/search` later combines:
- Text:
  - BM25 sidecar + dense Qdrant text vectors (hybrid or selected method)
- Image:
  - Qdrant image multivectors (ColQwen)

So indexing writes all retrieval artifacts needed for runtime search and generation.
