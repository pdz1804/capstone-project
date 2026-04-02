"""BM25 on-disk store (sparse leg of hybrid search; dense leg is Qdrant)."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import is_s3_storage_backend
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)

RETRIEVAL_DOCS_REL = "retrieval/documents.json"
RETRIEVAL_BM25_REL = "retrieval/bm25_index.pkl"

def save_documents_snapshot(documents: List[Dict[str, Any]], path: Path, user_id: str | None = None) -> None:
    if is_s3_storage_backend():
        st = get_file_storage(user_id)
        if isinstance(st, S3FileStorage):
            body = pickle.dumps(documents)
            st.write_processed_bytes(RETRIEVAL_DOCS_REL + ".pkl", body, content_type="application/octet-stream")
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(documents, f)


def load_documents_snapshot(path: Path, user_id: str | None = None) -> List[Dict[str, Any]]:
    if is_s3_storage_backend():
        st = get_file_storage(user_id)
        if isinstance(st, S3FileStorage):
            body = st.read_processed_bytes(RETRIEVAL_DOCS_REL + ".pkl")
            if not body:
                return []
            try:
                docs = pickle.loads(body)
                return docs if isinstance(docs, list) else []
            except Exception as e:
                logger.error("Failed to load S3 documents snapshot: %s", e)
                return []
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            docs = pickle.load(f)
        return docs if isinstance(docs, list) else []
    except Exception as e:
        logger.error("Failed to load documents snapshot: %s", e)
        return []


def save_bm25_index(documents: List[Dict[str, Any]], path: Path, user_id: str | None = None) -> None:
    from src.retrieval.rag_retrievers import SimpleBM25Retriever

    r = SimpleBM25Retriever()
    r.index_documents(documents)
    payload = {
        "documents": r.documents,
        "tokenized_docs": r.tokenized_docs,
        "bm25": r.bm25,
    }
    if is_s3_storage_backend():
        st = get_file_storage(user_id)
        if isinstance(st, S3FileStorage):
            st.write_processed_bytes(RETRIEVAL_BM25_REL, pickle.dumps(payload), content_type="application/octet-stream")
            logger.info("Saved BM25 index (%s chunks) to %s", len(documents), st.processed_uri(RETRIEVAL_BM25_REL))
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    logger.info("Saved BM25 index (%s chunks) to %s", len(documents), path)


def load_bm25_index(path: Path, user_id: str | None = None) -> Optional[Dict[str, Any]]:
    if is_s3_storage_backend():
        st = get_file_storage(user_id)
        if isinstance(st, S3FileStorage):
            body = st.read_processed_bytes(RETRIEVAL_BM25_REL)
            if not body:
                return None
            try:
                return pickle.loads(body)
            except Exception as e:
                logger.error("Failed to load BM25 from S3: %s", e)
                return None
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
