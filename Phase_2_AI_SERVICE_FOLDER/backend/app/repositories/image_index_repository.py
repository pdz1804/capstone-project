"""Qdrant persistence for ColQwen multi-vector image pages."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
    Distance,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
    PayloadSchemaType,
)

logger = logging.getLogger(__name__)


class ImageIndexRepository:
    def __init__(
        self,
        client: QdrantClient,
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
        sq = self.storage_quantization
        if sq == "scalar":
            return ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            )
        if sq == "binary":
            return BinaryQuantization(binary=BinaryQuantizationConfig(always_ram=True))
        return None

    def ensure_collection(self, recreate: bool = False) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            if recreate:
                self.client.delete_collection(self.collection_name)
            else:
                return
        params = VectorParams(
            size=self.embedding_dim,
            distance=Distance.DOT,
            multivector_config=MultiVectorConfig(comparator=MultiVectorComparator.MAX_SIM),
            quantization_config=self._quant_config(),
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={self.vector_name: params},
        )
        for field_name, field_type in (
            ("source", PayloadSchemaType.KEYWORD),
            ("page", PayloadSchemaType.INTEGER),
            ("source_path", PayloadSchemaType.KEYWORD),
        ):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception as e:
                logger.debug("Payload index %s: %s", field_name, e)

    def upsert_pages(
        self,
        ids: Sequence[str],
        multivectors: List[List[List[float]]],
        payloads: List[Dict[str, Any]],
        batch_size: int = 8,
    ) -> None:
        n = len(ids)
        if len(multivectors) != n or len(payloads) != n:
            raise ValueError("ids, multivectors, payloads length mismatch")
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            points: List[PointStruct] = []
            for i in range(start, end):
                points.append(
                    PointStruct(
                        id=ids[i],
                        vector={self.vector_name: multivectors[i]},
                        payload=payloads[i],
                    )
                )
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def search(self, query_multivec: List[List[float]], limit: int = 5) -> List[Dict[str, Any]]:
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_multivec,
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
