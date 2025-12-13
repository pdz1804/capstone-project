"""
Unified RAG Pipeline Package

This package combines document processing and information retrieval
into a complete RAG (Retrieval-Augmented Generation) system.

Components:
- processor/: Document processing pipeline (normalization, media, Docling)
- retrieval/: Information retrieval systems (BM25, Dense, Hybrid, ColBERT, ColQwen)
- unified_rag_pipeline.py: Main orchestrator combining both pipelines
"""

__version__ = "1.0.0"
__author__ = "QPhu (Processor) + NKhoi (Retrieval)"
__description__ = "Unified RAG Pipeline combining document processing and information retrieval"

from .unified_rag_pipeline import UnifiedRAGPipeline, UnifiedRAGConfig

__all__ = [
    "UnifiedRAGPipeline",
    "UnifiedRAGConfig"
]
