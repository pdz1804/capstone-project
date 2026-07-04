"""
Unified RAG Pipeline Package

This package combines document processing and information retrieval
into a complete RAG (Retrieval-Augmented Generation) system.

Components:
- processor/: Document processing pipeline (normalization, media, Docling)
- retrieval/: Information retrieval systems (BM25, Dense, Hybrid, ColBERT, ColQwen)
- unified_rag_pipeline.py: Main orchestrator combining both pipelines
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "1.0.0"
__author__ = "QPhu (Processor) + NKhoi (Retrieval)"
__description__ = "Unified RAG Pipeline combining document processing and information retrieval"

# Keep these imports lazy to avoid circular imports when lower-level processor
# modules import `src.*` helpers during package initialization.
if TYPE_CHECKING:
    from .unified_rag_pipeline import UnifiedRAGConfig, UnifiedRAGPipeline


def __getattr__(name: str):
    if name in {"UnifiedRAGPipeline", "UnifiedRAGConfig"}:
        from .unified_rag_pipeline import UnifiedRAGConfig, UnifiedRAGPipeline

        return {"UnifiedRAGPipeline": UnifiedRAGPipeline, "UnifiedRAGConfig": UnifiedRAGConfig}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["UnifiedRAGPipeline", "UnifiedRAGConfig"]
