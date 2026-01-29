"""
Text Chunking Module

This module provides text chunking functionality for RAG systems,
splitting documents into smaller, semantically meaningful chunks.
"""

from .chunker import (
    ChunkingConfig,
    TextChunker,
    chunk_documents,
    chunk_text
)

__all__ = [
    "ChunkingConfig",
    "TextChunker",
    "chunk_documents",
    "chunk_text"
]

