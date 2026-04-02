# Qdrant Multitenancy Standard

This backend uses payload-based multitenancy with one shared collection per modality.

## Collection Strategy

- Text vectors: one shared collection (`qdrant.text_collection`)
- Image vectors: one shared collection (`qdrant.image_collection`)
- Tenant isolation: payload key `user_id` on every point

Per-user collections are deprecated and treated as legacy.

## Required Query/Delete Rules

- Every search MUST include a Qdrant filter on `user_id`.
- Every clear/remove action MUST scope deletion by `user_id` (except explicit admin operations).
- The backend creates payload indexes for:
  - `user_id` (keyword, tenant-aware when supported by server/client)
  - text: `source`, `chunk_id`
  - image: `source`, `page`, `source_path`

## Performance Defaults

- Text vectors: `on_disk=true`, scalar quantization (`int8`) by default.
- Image vectors (ColQwen multivector): `on_disk=true`, scalar quantization (`int8`) by default.
- Upserts are batched and default to `wait=false` for higher throughput.

## BM25 Storage (S3 Mode)

BM25 is not stored in Qdrant. In S3 backend mode, BM25 sidecars are persisted in the processed bucket under the active user prefix:

- `retrieval/bm25_index.pkl`
- `retrieval/documents.json.pkl`

In local backend mode, they stay on disk under `output/retrieval/`.

## Legacy Collection Cleanup

Legacy per-user collections matching `<base>_<suffix>` can be removed safely after migration.

- Text base: `qdrant.text_collection`
- Image base: `qdrant.image_collection`

Current clear-index flows also attempt to drop these legacy suffixed collections.
