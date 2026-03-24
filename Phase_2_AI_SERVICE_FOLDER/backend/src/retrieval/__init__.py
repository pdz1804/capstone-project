"""
Information Retrieval Pipeline

This module handles various retrieval strategies for RAG systems,
including sparse, dense, hybrid, reranking, and multi-modal retrieval.

Text-based RAG:
- BM25 (sparse retrieval)
- Dense (MiniLM-L6-v2 embeddings)
- Hybrid (BM25 + Dense with RRF fusion)
- Reranking (BGE-Large, MiniLM cross-encoder)

Image-based RAG:
- ColQwen (vision-language model for PDF page retrieval)
"""

from .rag_retrievers import (
    RAGRetrieverManager,
    create_rag_retriever,
    load_rag_retriever,
    SimpleBM25Retriever,
    SimpleDenseRetriever,
    SimpleHybridRetriever,
    CrossEncoderReranker,
    BaseRetriever
)

from .image_retrievers import (
    ImageRAGManager,
    create_image_retriever,
    load_image_retriever,
    ColQwenRetriever,
    BaseImageRetriever
)

from ..chunking.chunker import (
    TextChunker,
    ChunkingConfig
)

__all__ = [
    # Text RAG Retrievers
    "RAGRetrieverManager",
    "create_rag_retriever",
    "load_rag_retriever",
    "SimpleBM25Retriever",
    "SimpleDenseRetriever", 
    "SimpleHybridRetriever",
    "CrossEncoderReranker",
    "BaseRetriever",
    # Image RAG Retrievers
    "ImageRAGManager",
    "create_image_retriever",
    "load_image_retriever",
    "ColQwenRetriever",
    "BaseImageRetriever",
    # Chunking
    "TextChunker",
    "ChunkingConfig",
]
