"""ColQwen query embedding + Qdrant MaxSim image search."""

from __future__ import annotations

import logging
import json
import threading
from typing import Any, Dict, List

from app.core.paths import qdrant_collection_names_for_user, workspace_paths_for_user
from app.repositories import ImageIndexRepository, build_qdrant_client
from app.services.colqwen_inference import ColQwenInferenceService

logger = logging.getLogger(__name__)


class ImageSearchService:
    _colqwen_lock = threading.Lock()
    _colqwen_cache: Dict[str, ColQwenInferenceService] = {}
    _prepared_collections_lock = threading.Lock()
    _prepared_collections: set[str] = set()

    def __init__(self, yaml_config: Dict[str, Any], user_id: str | None = None):
        self.cfg = yaml_config
        self._client = build_qdrant_client(yaml_config)
        q = yaml_config.get("qdrant", {}) or {}
        quant = q.get("image_storage_quantization", "scalar")
        paths = workspace_paths_for_user(user_id)
        self._user_id = paths.user_id
        _, img_col = qdrant_collection_names_for_user(
            q.get("text_collection", "edu_text_chunks"),
            q.get("image_collection", "edu_image_pages"),
            paths.user_id,
        )
        self._repo = ImageIndexRepository(
            self._client,
            collection_name=img_col,
            vector_name=q.get("image_vector_name", "colpali_multivec"),
            embedding_dim=128,
            storage_quantization=quant,
        )
        self._collection_name = str(img_col)
        cfg_key = json.dumps(yaml_config or {}, sort_keys=True, default=str)
        with ImageSearchService._colqwen_lock:
            cached = ImageSearchService._colqwen_cache.get(cfg_key)
            if cached is None:
                cached = ColQwenInferenceService(yaml_config)
                ImageSearchService._colqwen_cache[cfg_key] = cached
            self._colqwen = cached
    def _ensure_collection_once(self) -> None:
        with ImageSearchService._prepared_collections_lock:
            if self._collection_name in ImageSearchService._prepared_collections:
                return
        self._repo.ensure_collection(recreate=False)
        with ImageSearchService._prepared_collections_lock:
            ImageSearchService._prepared_collections.add(self._collection_name)

    def search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        qvec = self._colqwen.embed_query(query)
        # Ensure payload indexes (notably user_id) exist on pre-migration collections.
        self._ensure_collection_once()
        hits = self._repo.search(qvec, limit=top_k, user_id=self._user_id)
        results: List[Dict[str, Any]] = []
        for rank, hit in enumerate(hits, start=1):
            pl = hit.get("payload") or {}
            source = pl.get("source", "")
            page = int(pl.get("page", 0) or 0)
            results.append(
                {
                    "id": f"{source}_page_{page}",
                    "source": source,
                    "source_path": pl.get("source_path", ""),
                    "storage_uri": pl.get("storage_uri", ""),
                    "storage_backend": pl.get("storage_backend", ""),
                    "page": page,
                    "total_pages": pl.get("total_pages", 0),
                    "score": float(hit.get("score", 0.0)),
                    "rank": rank,
                    "text": f"[Image Page {page} from {source}]",
                    "retrieval_type": "colqwen_qdrant",
                }
            )
        return results
