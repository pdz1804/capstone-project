"""Pipeline status aligned with Qdrant + BM25 (no FAISS).

GET /api/status hits Qdrant (collection metadata) per uncached request. A short in-process TTL cache
avoids hammering Qdrant when the UI polls. Use ?fresh=true after index/process to force refresh.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Query

from app.api.deps import storage_user_id
from app.core.paths import merged_runtime_settings, qdrant_collection_names_for_user, workspace_paths_for_user
from app.repositories import ImageIndexRepository, TextIndexRepository, build_qdrant_client

router = APIRouter(prefix="/api", tags=["status"])

# (monotonic_ts, payload) per storage user — avoids repeated Qdrant round-trips from UI polling.
_status_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_status_cache_lock = threading.Lock()
_user_compute_locks: Dict[str, threading.Lock] = {}
_user_compute_locks_guard = threading.Lock()


def _cache_ttl_seconds() -> float:
    return float(os.getenv("STATUS_QDRANT_CACHE_TTL_SECONDS", "20"))


def _lock_for_user(user_id: str) -> threading.Lock:
    with _user_compute_locks_guard:
        if user_id not in _user_compute_locks:
            _user_compute_locks[user_id] = threading.Lock()
        return _user_compute_locks[user_id]


def _cache_get(user_id: str) -> Optional[Dict[str, Any]]:
    ttl = _cache_ttl_seconds()
    if ttl <= 0:
        return None
    now = time.monotonic()
    with _status_cache_lock:
        row = _status_cache.get(user_id)
        if not row:
            return None
        ts, payload = row
        if now - ts > ttl:
            del _status_cache[user_id]
            return None
        return dict(payload)


def _cache_set(user_id: str, payload: Dict[str, Any]) -> None:
    if _cache_ttl_seconds() <= 0:
        return
    with _status_cache_lock:
        _status_cache[user_id] = (time.monotonic(), dict(payload))


def _embedding_dim(model_name: str) -> int:
    m = (model_name or "").lower()
    if "minilm-l6" in m:
        return 384
    if "large" in m:
        return 1024
    return 384


def _compute_pipeline_status(user_id: str) -> Dict[str, Any]:
    cfg = merged_runtime_settings()
    q = cfg.get("qdrant", {}) or {}
    tr_conf = cfg.get("text_retrieval", {}) or {}
    embed_model = tr_conf.get("embedding_model", "all-MiniLM-L6-v2")
    dim = _embedding_dim(embed_model)

    paths = workspace_paths_for_user(user_id)
    text_col, img_col = qdrant_collection_names_for_user(
        q.get("text_collection", "edu_text_chunks"),
        q.get("image_collection", "edu_image_pages"),
        paths.user_id,
    )

    indexed_docs = 0
    n_sources = 0
    doc_list = []
    if paths.documents_json_path.exists():
        try:
            with open(paths.documents_json_path, "r", encoding="utf-8") as f:
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
            collection_name=text_col,
            vector_name=q.get("text_vector_name", "text"),
            vector_size=dim,
        )
        i_repo = ImageIndexRepository(
            client,
            collection_name=img_col,
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


@router.get("/status")
async def status(
    user_id: str = Depends(storage_user_id),
    fresh: bool = Query(
        False,
        description="If true, bypass the server-side cache and query Qdrant again (use after index/process).",
    ),
) -> Dict[str, Any]:
    ttl = _cache_ttl_seconds()
    with _lock_for_user(user_id):
        if not fresh and ttl > 0:
            cached = _cache_get(user_id)
            if cached is not None:
                return cached

        payload = _compute_pipeline_status(user_id)
        _cache_set(user_id, payload)
        return payload
