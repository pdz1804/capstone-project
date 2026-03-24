"""BM25 on-disk store (sparse leg of hybrid search; dense leg is Qdrant)."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def save_bm25_index(documents: List[Dict[str, Any]], path: Path) -> None:
    from src.retrieval.rag_retrievers import SimpleBM25Retriever

    path.parent.mkdir(parents=True, exist_ok=True)
    r = SimpleBM25Retriever()
    r.index_documents(documents)
    with open(path, "wb") as f:
        pickle.dump(
            {
                "documents": r.documents,
                "tokenized_docs": r.tokenized_docs,
                "bm25": r.bm25,
            },
            f,
        )
    logger.info("Saved BM25 index (%s chunks) to %s", len(documents), path)


def load_bm25_index(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.error("Failed to load BM25: %s", e)
        return None


def bm25_search(data: Dict[str, Any], query: str, top_k: int) -> List[Dict[str, Any]]:
    """Run search using pickled bm25 + documents (same layout as SimpleBM25Retriever)."""
    bm25 = data.get("bm25")
    documents: List[Dict[str, Any]] = data.get("documents") or []
    if bm25 is None or not documents:
        return []

    from src.retrieval.rag_retrievers import SimpleBM25Retriever

    r = SimpleBM25Retriever()
    r.documents = documents
    r.tokenized_docs = data.get("tokenized_docs") or []
    r.bm25 = bm25
    r.is_indexed = True
    return r.search(query, top_k)
