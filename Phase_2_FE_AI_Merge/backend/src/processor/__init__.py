"""
Document Processing Pipeline

This module handles document ingestion, normalization, and processing
for RAG systems.
"""

from .pipeline import DocumentProcessingPipeline, PipelineConfig
from .normalizer import DocumentNormalizer, NormalizerConfig
from .media_processor import MediaProcessor, MediaProcessorConfig
from .document_processor import MultimodalDocumentProcessor, ProcessingConfig
from .consolidator import Stage4Consolidator, ConsolidatorConfig
from .xlsx_reader_v2 import process_excel_file
from .chunk_enhancer import (
    ChunkEnhancement,
    FrameMetadata,
    ChunkDescriptionGenerator,
    FrameMetadataBuilder,
    EnhancedChunkProcessor
)

__all__ = [
    "DocumentProcessingPipeline",
    "PipelineConfig",
    "DocumentNormalizer", 
    "NormalizerConfig",
    "MediaProcessor",
    "MediaProcessorConfig", 
    "MultimodalDocumentProcessor",
    "ProcessingConfig",
    "Stage4Consolidator",
    "ConsolidatorConfig",
    "ChunkEnhancement",
    "FrameMetadata",
    "ChunkDescriptionGenerator",
    "FrameMetadataBuilder",
    "EnhancedChunkProcessor"
]