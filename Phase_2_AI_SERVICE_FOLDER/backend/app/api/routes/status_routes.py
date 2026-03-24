"""Pipeline status aligned with Qdrant + BM25 (no FAISS)."""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter

from app.core.paths import DOCUMENTS_JSON_PATH, merged_runtime_settings
from app.repositories import ImageIndexRepository, TextIndexRepository, build_qdrant_client

router = APIRouter(prefix="/api", tags=["status"])


def _embedding_dim(model_name: str) -> int:
    m = (model_name or "").lower()
    if "minilm-l6" in m:
        return 384
    if "large" in m:
        return 1024
    return 384


@router.get("/status")
async def status() -> Dict[str, Any]:
    cfg = merged_runtime_settings()
    q = cfg.get("qdrant", {}) or {}
    tr_conf = cfg.get("text_retrieval", {}) or {}
    embed_model = tr_conf.get("embedding_model", "all-MiniLM-L6-v2")
    dim = _embedding_dim(embed_model)

    indexed_docs = 0
    n_sources = 0
    doc_list = []
    if DOCUMENTS_JSON_PATH.exists():
        try:
            with open(DOCUMENTS_JSON_PATH, "r", encoding="utf-8") as f:
                doc_list = json.load(f)
            indexed_docs = len(doc_list)
            n_sources = len({d.get("source", "") for d in doc_list if d.get("source")})
        except Exception:
            pass

    t_count = 0
    i_count = 0
    try:
        client = build_qdrant_client(cfg)
        t_repo = TextIndexRepository(
            client,
            collection_name=q.get("text_collection", "edu_text_chunks"),
            vector_name=q.get("text_vector_name", "text"),
            vector_size=dim,
        )
        i_repo = ImageIndexRepository(
            client,
            collection_name=q.get("image_collection", "edu_image_pages"),
            vector_name=q.get("image_vector_name", "colpali_multivec"),
            embedding_dim=128,
            storage_quantization=q.get("image_storage_quantization", "scalar"),
        )
        t_count = t_repo.count_points()
        i_count = i_repo.count_points()
    except Exception:
        pass

    text_index = {
        "chunks": indexed_docs,
        "qdrant_points": t_count,
        "docs": n_sources,
        "retrievers": ["bm25", "dense", "hybrid"],
        "dense_backend": "qdrant",
        "embedding_model": embed_model,
    }
    image_index = {
        "pages": i_count,
        "retrievers": ["colqwen"],
        "vector_store": "qdrant",
    }
    ready = indexed_docs > 0 or i_count > 0

    return {
        "ready": ready,
        "indexed_docs": indexed_docs,
        "image_pages": i_count,
        "text_index": text_index,
        "image_index": image_index,
    }
