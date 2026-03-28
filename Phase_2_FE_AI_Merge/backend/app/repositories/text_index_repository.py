"""Qdrant persistence for dense text chunks (single-vector per point)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Sequence

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

from app.repositories.qdrant_point_ids import logical_id_to_qdrant_point_id

logger = logging.getLogger(__name__)


def _qdrant_models():
    from qdrant_client.models import Distance, PointStruct, VectorParams

    return Distance, PointStruct, VectorParams


class TextIndexRepository:
    def __init__(
        self,
        client: "QdrantClient",
        collection_name: str,
        vector_name: str = "text",
        vector_size: int = 384,
    ):
        self.client = client
        self.collection_name = collection_name
        self.vector_name = vector_name
        self.vector_size = vector_size

    def ensure_collection(self, recreate: bool = False) -> None:
        Distance, _, VectorParams = _qdrant_models()

        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            if recreate:
                self.client.delete_collection(self.collection_name)
            else:
                return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.vector_name: VectorParams(size=self.vector_size, distance=Distance.COSINE),
            },
        )
        logger.info("Created Qdrant text collection %s (dim=%s)", self.collection_name, self.vector_size)

    def upsert_chunks(
        self,
        ids: Sequence[str],
        embeddings: Any,
        payloads: List[Dict[str, Any]],
        batch_size: int = 64,
    ) -> None:
        _, PointStruct, _ = _qdrant_models()
        import numpy as np

        emb = np.asarray(embeddings)
        if emb.ndim != 2:
            raise ValueError("embeddings must be 2-D")
        n = len(ids)
        if emb.shape[0] != n or len(payloads) != n:
            raise ValueError("ids, embeddings, payloads length mismatch")

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            points: List[Any] = []
            for i in range(start, end):
                vec = emb[i].tolist() if hasattr(emb[i], "tolist") else list(emb[i])
                points.append(
                    PointStruct(
                        id=logical_id_to_qdrant_point_id(str(ids[i])),
                        vector={self.vector_name: vec},
                        payload=payloads[i],
                    )
                )
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=self.vector_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        out = []
        for p in res.points:
            out.append(
                {
                    "id": p.id,
                    "score": float(p.score) if p.score is not None else 0.0,
                    "payload": p.payload or {},
                }
            )
        return out

    def count_points(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return int(info.points_count)
        except Exception:
            return 0

    def delete_by_source(self, source_value: str) -> int:
        """Remove all points whose payload ``source`` equals ``source_value`` (exact match)."""
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        flt = Filter(must=[FieldCondition(key="source", match=MatchValue(value=source_value))])
        try:
            cnt = self.client.count(
                collection_name=self.collection_name,
                count_filter=flt,
                exact=True,
            ).count
        except Exception:
            cnt = 0
        if cnt == 0:
            return 0
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=flt),
            wait=True,
        )
        return int(cnt)

    def clear_all_points(self) -> None:
        """Drop and recreate the text collection (empty)."""
        self.ensure_collection(recreate=True)
