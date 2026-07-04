"""
Text Chunking Module

This module provides text chunking functionality for RAG systems,
splitting documents into smaller, semantically meaningful chunks.

Includes table-aware chunking for Excel/spreadsheet documents.
"""

from .chunker import (
    ChunkingConfig,
    TextChunker,
    chunk_documents,
    chunk_text
)

from .excel_chunker import (
    ExcelChunkingConfig,
    ExcelTableChunker,
    chunk_excel_json,
)

from .excel_preprocessor import (
    ExcelPreprocessor,
    preprocess_excel_for_rag,
)

__all__ = [
    "ChunkingConfig",
    "TextChunker",
    "chunk_documents",
    "chunk_text",
    # Excel-specific
    "ExcelChunkingConfig",
    "ExcelTableChunker",
    "chunk_excel_json",
    "ExcelPreprocessor",
    "preprocess_excel_for_rag",
]

