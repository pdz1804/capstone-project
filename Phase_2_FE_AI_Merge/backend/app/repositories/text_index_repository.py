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
        storage_quantization: str = "scalar",
        on_disk_vectors: bool = True,
    ):
        self.client = client
        self.collection_name = collection_name
        self.vector_name = vector_name
        self.vector_size = vector_size
        self.storage_quantization = storage_quantization
        self.on_disk_vectors = on_disk_vectors

    def _quant_config(self):
        from qdrant_client.models import (
            BinaryQuantization,
            BinaryQuantizationConfig,
            ScalarQuantization,
            ScalarQuantizationConfig,
            ScalarType,
        )

        sq = (self.storage_quantization or "").strip().lower()
        if sq == "scalar":
            return ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=False,
                )
            )
        if sq == "binary":
            return BinaryQuantization(binary=BinaryQuantizationConfig(always_ram=False))
        return None

    def _ensure_payload_indexes(self) -> None:
        from qdrant_client.models import PayloadSchemaType

        fields = (
            ("user_id", PayloadSchemaType.KEYWORD),
            ("source", PayloadSchemaType.KEYWORD),
            ("chunk_id", PayloadSchemaType.KEYWORD),
        )
        for field_name, field_schema in fields:
            ok = False
            attempts = [field_schema]
            # Some client/server combos accept plain strings more reliably.
            if field_schema == PayloadSchemaType.KEYWORD:
                attempts.append("keyword")
            last_err: Exception | None = None
            for schema in attempts:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=schema,
                    )
                    ok = True
                    break
                except Exception as e:
                    last_err = e
            if not ok:
                msg = f"Failed to create payload index '{field_name}' on {self.collection_name}: {last_err}"
                if field_name == "user_id":
                    # Hard-fail: tenant filter queries depend on this index.
                    raise RuntimeError(msg) from last_err
                logger.warning(msg)

    def ensure_collection(self, recreate: bool = False) -> None:
        Distance, _, VectorParams = _qdrant_models()

        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            if recreate:
                self.client.delete_collection(self.collection_name)
            else:
                self._ensure_payload_indexes()
                return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.vector_name: VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                    on_disk=bool(self.on_disk_vectors),
                    quantization_config=self._quant_config(),
                ),
            },
        )
        self._ensure_payload_indexes()
        logger.info("Created Qdrant text collection %s (dim=%s)", self.collection_name, self.vector_size)

    def upsert_chunks(
        self,
        ids: Sequence[str],
        embeddings: Any,
        payloads: List[Dict[str, Any]],
        batch_size: int = 64,
        wait: bool = False,
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
            self.client.upsert(collection_name=self.collection_name, points=points, wait=wait)

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        qfilter = None
        if user_id:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            qfilter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=self.vector_name,
            limit=limit,
            query_filter=qfilter,
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

    def count_points(self, user_id: str | None = None) -> int:
        try:
            if user_id:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
                return int(
                    self.client.count(
                        collection_name=self.collection_name,
                        count_filter=flt,
                        exact=True,
                    ).count
                )
            info = self.client.get_collection(self.collection_name)
            return int(info.points_count)
        except Exception:
            return 0

    def list_sources(self, user_id: str | None = None, limit: int = 50000) -> set[str]:
        """
        Return distinct payload ``source`` values currently present in the text collection.
        Useful for per-file indexed-text status checks without relying on sidecar snapshots.
        """
        out: set[str] = set()
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            flt = None
            if user_id:
                flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])

            offset = None
            fetched = 0
            page_size = min(512, max(32, limit))
            while fetched < limit:
                points, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=flt,
                    with_payload=["source"],
                    with_vectors=False,
                    limit=min(page_size, limit - fetched),
                    offset=offset,
                )
                if not points:
                    break
                fetched += len(points)
                for p in points:
                    payload = p.payload or {}
                    src = payload.get("source")
                    if src:
                        out.add(str(src).strip().lower())
                if offset is None:
                    break
        except Exception:
            return set()
        return out

    def delete_by_source(self, source_value: str, user_id: str | None = None) -> int:
        """Remove all points whose payload ``source`` equals ``source_value`` (exact match)."""
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        must = [FieldCondition(key="source", match=MatchValue(value=source_value))]
        if user_id:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        flt = Filter(must=must)
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

    def delete_by_user(self, user_id: str) -> int:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
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
