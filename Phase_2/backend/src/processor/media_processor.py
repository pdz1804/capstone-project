"""
Media Processor Module

This module handles video and audio processing for the RAG pipeline.
Now delegates to media_processor_enhanced for advanced features:
- Extracts audio from video files with noise reduction
- Transcribes audio using Whisper with full parameters and word-level timestamps
- Performs intelligent transcript chunking (max 100 tokens per chunk)
- Extracts frames with duplicate removal and frame-level metadata
- Tracks complete provenance metadata and uniform chunk metadata

Based on Week0506_Mkhoi_OCR_ASR implementation with comprehensive enhancements.
"""

# Re-export everything from the enhanced version for backward compatibility.
# pipeline.py and unified_rag_pipeline.py import from this module;
# by delegating to media_processor_enhanced, all existing imports continue to work
# while gaining the new enhanced processing logic.

from .media_processor_enhanced import (
    # Configuration
    MediaProcessorConfig,
    # Core components
    AudioNoiseReducer,
    FrameDeduplicator,
    TranscriptChunker,
    AudioExtractor,
    AudioTranscriber,
    FrameExtractor,
    MediaProcessor,
    # Utility
    process_media,
    setup_logging,
    # Library availability flags
    TORCH_AVAILABLE,
    WHISPER_AVAILABLE,
    LIBROSA_AVAILABLE,
    MOVIEPY_AVAILABLE,
    CV2_AVAILABLE,
    NUMPY_AVAILABLE,
    PIL_AVAILABLE,
    SCIPY_AVAILABLE,
    IMAGEHASH_AVAILABLE,
)

__all__ = [
    "MediaProcessorConfig",
    "AudioNoiseReducer",
    "FrameDeduplicator",
    "TranscriptChunker",
    "AudioExtractor",
    "AudioTranscriber",
    "FrameExtractor",
    "MediaProcessor",
    "process_media",
]
