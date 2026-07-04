"""Load chunked documents from stage4_rag_ready (same rules as RAGRetrieverManager)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.core.paths import RETRIEVAL_DIR
from src.retrieval.rag_retrievers import RAGRetrieverManager


def load_documents_for_indexing(rag_ready_dir: Path, yaml_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    tr = yaml_config.get("text_retrieval", {}) or {}
    chunking = tr.get("chunking", {}) or {}
    mgr = RAGRetrieverManager(
        doc_dir=rag_ready_dir,
        index_dir=RETRIEVAL_DIR,
        chunk_size=int(chunking.get("chunk_size", 1000)),
        chunk_overlap=int(chunking.get("chunk_overlap", 200)),
        enable_chunking=chunking.get("enabled", True),
        reranker_model=None,
    )
    mgr.load_documents()
    return mgr.documents
