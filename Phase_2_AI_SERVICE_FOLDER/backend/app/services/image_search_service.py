"""ColQwen query embedding + Qdrant MaxSim image search."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.repositories import ImageIndexRepository, build_qdrant_client
from app.services.colqwen_inference import ColQwenInferenceService

logger = logging.getLogger(__name__)


class ImageSearchService:
    def __init__(self, yaml_config: Dict[str, Any]):
        self.cfg = yaml_config
        self._client = build_qdrant_client(yaml_config)
        q = yaml_config.get("qdrant", {}) or {}
        quant = q.get("image_storage_quantization", "scalar")
        self._repo = ImageIndexRepository(
            self._client,
            collection_name=q.get("image_collection", "edu_image_pages"),
            vector_name=q.get("image_vector_name", "colpali_multivec"),
            embedding_dim=128,
            storage_quantization=quant,
        )
        self._colqwen = ColQwenInferenceService(yaml_config)

    def search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        qvec = self._colqwen.embed_query(query)
        hits = self._repo.search(qvec, limit=top_k)
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
                    "page": page,
                    "total_pages": pl.get("total_pages", 0),
                    "score": float(hit.get("score", 0.0)),
                    "rank": rank,
                    "text": f"[Image Page {page} from {source}]",
                    "retrieval_type": "colqwen_qdrant",
                }
            )
        return results
