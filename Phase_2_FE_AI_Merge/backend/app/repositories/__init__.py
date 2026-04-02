"""Qdrant + BM25 repositories (lazy qdrant imports inside factory / repo methods where possible)."""

from app.repositories.bm25_store import (
    bm25_search,
    load_bm25_index,
    load_documents_snapshot,
    save_bm25_index,
    save_documents_snapshot,
)
from app.repositories.image_index_repository import ImageIndexRepository
from app.repositories.qdrant_factory import build_qdrant_client
from app.repositories.text_index_repository import TextIndexRepository

__all__ = [
    "bm25_search",
    "build_qdrant_client",
    "ImageIndexRepository",
    "load_bm25_index",
    "load_documents_snapshot",
    "save_bm25_index",
    "save_documents_snapshot",
    "TextIndexRepository",
]
