"""
Week070809 - Unified Document Processing Pipeline for RAG

A comprehensive document processing pipeline that handles any document type
through a three-stage architecture optimized for RAG systems.

Modules:
- normalizer: Stage 1 - Convert documents to PDF/Markdown
- media_processor: Stage 2 - Process video/audio files
- document_processor: Stage 3 - Process with Docling
- pipeline: Main orchestration script
"""

__version__ = "1.0.0"
__author__ = "HCMUT Capstone Team"

from .normalizer import DocumentNormalizer, NormalizerConfig
from .media_processor import MediaProcessor, MediaProcessorConfig
from .document_processor import MultimodalDocumentProcessor, ProcessingConfig
from .pipeline import DocumentProcessingPipeline, PipelineConfig

__all__ = [
    # Main pipeline
    "DocumentProcessingPipeline",
    "PipelineConfig",
    
    # Stage 1: Normalization
    "DocumentNormalizer",
    "NormalizerConfig",
    
    # Stage 2: Media Processing
    "MediaProcessor",
    "MediaProcessorConfig",
    
    # Stage 3: Document Processing
    "MultimodalDocumentProcessor",
    "ProcessingConfig",
]