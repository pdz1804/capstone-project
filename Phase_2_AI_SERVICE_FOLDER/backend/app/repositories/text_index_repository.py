"""Qdrant persistence for dense text chunks (single-vector per point)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)


class TextIndexRepository:
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_name: str = "text",
        vector_size: int = 384,
    ):
        self.client = client
        self.collection_name = collection_name
        self.vector_name = vector_name
        self.vector_size = vector_size

    def ensure_collection(self, recreate: bool = False) -> None:
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
        """embeddings: numpy array or list of lists, aligned with ids."""
        import numpy as np

        emb = np.asarray(embeddings)
        if emb.ndim != 2:
            raise ValueError("embeddings must be 2-D")
        n = len(ids)
        if emb.shape[0] != n or len(payloads) != n:
            raise ValueError("ids, embeddings, payloads length mismatch")

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            points: List[PointStruct] = []
            for i in range(start, end):
                vec = emb[i].tolist() if hasattr(emb[i], "tolist") else list(emb[i])
                points.append(
                    PointStruct(
                        id=ids[i],
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
