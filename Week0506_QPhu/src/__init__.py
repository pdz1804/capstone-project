"""
Multimodal Document Processor Package

This package provides comprehensive document processing capabilities
using Docling for multimodal RAG pipeline preparation.
"""

from .document_processor import MultimodalDocumentProcessor, ProcessingConfig

from .utils import (
    get_file_hash,
    get_processing_recommendations,
    format_file_size,
    format_duration,
    create_processing_summary,
    validate_processing_config,
    create_file_index
)

__version__ = "1.0.0"
__author__ = "HCMUT RAG Pipeline Team"

__all__ = [
    "MultimodalDocumentProcessor",
    "ProcessingConfig",
    "get_file_hash",
    "get_processing_recommendations", 
    "format_file_size",
    "format_duration",
    "create_processing_summary",
    "validate_processing_config",
    "create_file_index"
]