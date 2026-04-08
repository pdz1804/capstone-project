"""Qdrant persistence for ColQwen multi-vector image pages."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Sequence

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

from app.repositories.qdrant_point_ids import logical_id_to_qdrant_point_id

logger = logging.getLogger(__name__)


class ImageIndexRepository:
    def __init__(
        self,
        client: "QdrantClient",
        collection_name: str,
        vector_name: str = "colpali_multivec",
        embedding_dim: int = 128,
        storage_quantization: str = "scalar",
    ):
        self.client = client
        self.collection_name = collection_name
        self.vector_name = vector_name
        self.embedding_dim = embedding_dim
        self.storage_quantization = storage_quantization

    def _quant_config(self):
        from qdrant_client.models import (
            BinaryQuantization,
            BinaryQuantizationConfig,
            ScalarQuantization,
            ScalarQuantizationConfig,
            ScalarType,
        )

        sq = self.storage_quantization
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
            ("page", PayloadSchemaType.INTEGER),
            ("source_path", PayloadSchemaType.KEYWORD),
        )
        for field_name, field_schema in fields:
            ok = False
            attempts = [field_schema]
            if field_schema == PayloadSchemaType.KEYWORD:
                attempts.append("keyword")
            if field_schema == PayloadSchemaType.INTEGER:
                attempts.append("integer")
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
                    raise RuntimeError(msg) from last_err
                logger.warning(msg)

    def ensure_collection(self, recreate: bool = False) -> None:
        from qdrant_client.models import (
            Distance,
            MultiVectorComparator,
            MultiVectorConfig,
            VectorParams,
        )

        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            if recreate:
                self.client.delete_collection(self.collection_name)
            else:
                self._ensure_payload_indexes()
                return
        params = VectorParams(
            size=self.embedding_dim,
            distance=Distance.DOT,
            multivector_config=MultiVectorConfig(comparator=MultiVectorComparator.MAX_SIM),
            quantization_config=self._quant_config(),
            on_disk=True,
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={self.vector_name: params},
        )
        self._ensure_payload_indexes()

    def upsert_pages(
        self,
        ids: Sequence[str],
        multivectors: List[List[List[float]]],
        payloads: List[Dict[str, Any]],
        batch_size: int = 8,
        wait: bool = False,
    ) -> None:
        from qdrant_client.models import PointStruct

        n = len(ids)
        if len(multivectors) != n or len(payloads) != n:
            raise ValueError("ids, multivectors, payloads length mismatch")
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            points: List[Any] = []
            for i in range(start, end):
                points.append(
                    PointStruct(
                        id=logical_id_to_qdrant_point_id(str(ids[i])),
                        vector={self.vector_name: multivectors[i]},
                        payload=payloads[i],
                    )
                )
            self.client.upsert(collection_name=self.collection_name, points=points, wait=wait)

    def search(
        self, query_multivec: List[List[float]], limit: int = 5, user_id: str | None = None
    ) -> List[Dict[str, Any]]:
        qfilter = None
        if user_id:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            qfilter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_multivec,
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
        Return distinct payload ``source`` values currently present in the image collection.
        Useful for per-file "indexed_image" status checks without false positives.
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

    def delete_by_pdf_name(self, pdf_filename: str, user_id: str | None = None) -> int:
        """Remove pages indexed with payload ``source`` == PDF basename (e.g. ``report.pdf``)."""
        return self.delete_by_source(pdf_filename, user_id=user_id)

    def delete_by_source(self, source_value: str, user_id: str | None = None) -> int:
        """Remove pages indexed with payload ``source`` == ``source_value`` (exact match)."""
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

    def clear_all_points(self) -> None:
        """Drop and recreate the image collection (empty)."""
        self.ensure_collection(recreate=True)

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
