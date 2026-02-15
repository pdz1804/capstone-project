# Media Processing Enhancements — Phase 2 Backend

> **Version**: 1.0  
> **Date**: 2025-07-18  
> **Scope**: Transcript chunking, frame extraction, uniform metadata, chunk enhancement  
> **Backward compatible**: Yes — all existing pipeline imports and CLI remain unchanged

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Changes](#architecture-changes)
3. [Uniform Metadata Schema](#uniform-metadata-schema)
4. [Enhanced Media Processor](#enhanced-media-processor)
5. [AudioNoiseReducer](#audionoiserreducer)
6. [FrameDeduplicator](#framededuplicator)
7. [TranscriptChunker with Uniform Metadata](#transcriptchunker-with-uniform-metadata)
8. [Frame–Chunk Bidirectional Association](#framechunk-bidirectional-association)
9. [Markdown Transcript Export](#markdown-transcript-export)
10. [Chunk Enhancer (LLM Descriptions)](#chunk-enhancer-llm-descriptions)
11. [Document Text Chunking Updates](#document-text-chunking-updates)
12. [Backward Compatibility](#backward-compatibility)
13. [File Change Summary](#file-change-summary)

---

## Overview

These enhancements upgrade the Phase 2 backend media processing pipeline with logic originally prototyped in `Phase_2_PDZ_001`. The key improvements are:

| Feature | Description |
|---------|-------------|
| **Uniform metadata** | Every chunk and frame carries a consistent set of metadata fields (`original_file`, `uploaded_timestamp`, `content_type`, etc.) |
| **Audio noise reduction** | High-pass Butterworth filter removes low-frequency noise before transcription |
| **Frame deduplication** | Perceptual hashing (pHash) skips near-duplicate frames |
| **Enhanced Whisper** | Word-level timestamps, temperature scheduling, compression ratio threshold |
| **Token-based transcript chunking** | Splits transcripts by token count (max 100 tokens) with segment alignment |
| **Frame ↔ Chunk association** | Bidirectional mapping between frames and transcript chunks by timestamp |
| **Markdown export** | `.md` transcript output for compatibility with Stage 3 Docling |
| **LLM chunk descriptions** | Optional OpenAI-powered one-sentence summaries per chunk |

---

## Architecture Changes

### Before

```
pipeline.py  →  media_processor.py (803-line monolithic file)
                 ├── MediaProcessorConfig
                 └── MediaProcessor
```

### After

```
pipeline.py  →  media_processor.py (thin re-export wrapper)
                 └── media_processor_enhanced.py (full implementation)
                      ├── MediaProcessorConfig      (+ backward-compat fields)
                      ├── AudioNoiseReducer          (NEW)
                      ├── FrameDeduplicator           (NEW)
                      ├── TranscriptChunker           (NEW — token-based)
                      ├── AudioExtractor
                      ├── AudioTranscriber            (+ enhanced Whisper params)
                      ├── FrameExtractor              (+ dedup, uniform metadata)
                      └── MediaProcessor              (+ .md export, frame-chunk assoc)

                 chunk_enhancer.py (NEW)
                      ├── ChunkDescriptionGenerator   (OpenAI LLM descriptions)
                      ├── FrameMetadataBuilder         (uniform frame metadata)
                      └── EnhancedChunkProcessor       (full enhancement pipeline)
```

`media_processor.py` is now a **thin wrapper** that re-exports all public symbols from `media_processor_enhanced.py`. This ensures `pipeline.py` and `unified_rag_pipeline.py` continue to work with zero changes.

---

## Uniform Metadata Schema

Every chunk and frame in the system now carries a consistent metadata schema:

### Transcript Text Chunks

```json
{
  "chunk_index": 0,
  "chunk_name": "lecture_video_chunk_0",
  "text": "...",
  "token_count": 87,
  "segment_indices": [0, 1, 2],
  "start_time": 0.0,
  "end_time": 12.5,
  "duration": 12.5,
  "original_file": "/path/to/lecture_video.mp4",
  "original_file_format": "mp4",
  "current_format": "text",
  "uploaded_timestamp": "2025-07-18T14:30:00",
  "content_type": "transcript_text",
  "associated_frames": [
    {
      "frame_path": "output/frames/frame_000150.jpg",
      "frame_index": 150,
      "frame_name": "lecture_video_frame_000150",
      "video_timestamp": 5.0
    }
  ]
}
```

### Extracted Frames

```json
{
  "frame_index": 150,
  "frame_name": "lecture_video_frame_000150",
  "frame_path": "output/frames/frame_000150.jpg",
  "original_file": "/path/to/lecture_video.mp4",
  "original_file_format": "mp4",
  "current_format": "jpg",
  "uploaded_timestamp": "2025-07-18T14:30:00",
  "video_timestamp": 5.0,
  "content_type": "extracted_frame",
  "frame_hash": "a1b2c3d4e5f6",
  "is_duplicate": false,
  "similarity_score": null,
  "associated_chunk_index": 0
}
```

### Document Text Chunks (from `chunker.py`)

```json
{
  "id": "doc1_chunk_0",
  "text": "...",
  "source": "/path/to/document.pdf",
  "doc_id": "doc1",
  "chunk_index": 0,
  "total_chunks": 15,
  "metadata": {
    "doc_id": "doc1",
    "chunk_index": 0,
    "chunk_name": "doc1_chunk_0",
    "total_chunks": 15,
    "source": "/path/to/document.pdf",
    "char_start": 0,
    "char_length": 980,
    "original_file": "/path/to/document.pdf",
    "original_file_format": "pdf",
    "current_format": "text",
    "uploaded_timestamp": "2025-07-18T14:30:00",
    "content_type": "document_text",
    "uniform_metadata_version": "1.0"
  }
}
```

---

## Enhanced Media Processor

### `MediaProcessorConfig` — New Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `export_md` | `bool` | `True` | Generate `.md` transcript for Stage 3 compatibility |
| `use_gpu` | `bool` | `True` | Backward-compat alias; syncs with `device` via `__post_init__` |
| `audio_channels` | `int` | `1` | Audio channel count for extraction |
| `chunk_duration` | `int` | `30` | Chunk duration in seconds (backward compat) |
| `chunk_overlap` | `float` | `1.0` | Overlap in seconds between audio chunks (backward compat) |

The `__post_init__` method ensures `device` and `use_gpu` stay in sync:

```python
def __post_init__(self):
    if self.use_gpu and self.device == "cpu":
        self.device = "cuda"
    elif not self.use_gpu and self.device != "cpu":
        self.device = "cpu"
```

### Enhanced Whisper Parameters

The `AudioTranscriber` now uses improved Whisper settings:

- **`word_timestamps=True`** — word-level timing for accurate chunking
- **Temperature schedule**: `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]` — progressive fallback
- **`compression_ratio_threshold=2.4`** — skip garbled segments
- **`condition_on_previous_text=True`** — better context flow

---

## AudioNoiseReducer

Applies a **high-pass Butterworth filter** (cutoff: 300 Hz by default) to remove low-frequency noise from extracted audio before Whisper transcription.

```python
class AudioNoiseReducer:
    def __init__(self, cutoff_freq=300, order=5)
    def reduce_noise(self, audio_path: str) -> str
```

**Dependencies**: `scipy.signal`, `librosa`, `soundfile`

---

## FrameDeduplicator

Uses **perceptual hashing (pHash)** via `imagehash` to detect and flag near-duplicate frames during extraction. Frames with similarity above the threshold are marked as duplicates but still saved (with `is_duplicate` metadata).

```python
class FrameDeduplicator:
    def __init__(self, hash_size=8, similarity_threshold=0.95)
    def compute_hash(self, frame) -> str
    def is_duplicate(self, frame) -> Tuple[bool, Optional[float]]
```

**Dependencies**: `imagehash`, `PIL/Pillow`

---

## TranscriptChunker with Uniform Metadata

The `TranscriptChunker` splits Whisper transcription segments into token-count-based chunks (default max: 100 tokens).

### Key Method: `chunk_transcript_with_uniform_metadata()`

```python
def chunk_transcript_with_uniform_metadata(
    self,
    segments: List[Dict],
    video_path: str
) -> List[Dict[str, Any]]
```

Each returned chunk includes:
- `chunk_index`, `chunk_name` — identification
- `text`, `token_count`, `segment_indices` — content
- `start_time`, `end_time`, `duration` — timing
- `original_file`, `original_file_format`, `current_format` — provenance
- `uploaded_timestamp`, `content_type` — uniform metadata
- `associated_frames: []` — placeholder for frame association

---

## Frame–Chunk Bidirectional Association

After both chunks and frames are produced, `MediaProcessor._associate_frames_with_chunks()` builds a **bidirectional mapping** based on timestamps:

1. For each frame, find the chunk whose `[start_time, end_time]` interval contains the frame's `video_timestamp`
2. Set `frame["associated_chunk_index"] = chunk_index`
3. Append frame reference to `chunk["associated_frames"]`

The results are persisted via `_resave_chunks_with_frames()` which updates the chunks JSON file on disk.

---

## Markdown Transcript Export

When `export_md=True` (default), the media processor generates a `.md` version of the transcript alongside the `.txt` and `.json` outputs. This is critical for **Stage 3 (Docling)** which processes markdown documents.

Format:

```markdown
# Transcript: lecture_video

**Source**: lecture_video.mp4
**Duration**: 00:03:30
**Segments**: 45
**Generated**: 2025-07-18T14:30:00

---

## Transcript

[00:00:00] First segment of speech here...

[00:00:05] Second segment continues...

---

*Generated by Enhanced Media Processor v2.0*
```

The `process_file()` method returns `transcript_md_path` and prefers the `.md` path as `transcript_path` for downstream pipeline compatibility.

---

## Chunk Enhancer (LLM Descriptions)

The new `chunk_enhancer.py` module provides **optional post-processing** to enrich chunks with LLM-generated descriptions and complete frame metadata.

### Classes

| Class | Purpose |
|-------|---------|
| `ChunkDescriptionGenerator` | Generates one-sentence summaries via OpenAI API |
| `FrameMetadataBuilder` | Constructs uniform metadata for frames |
| `EnhancedChunkProcessor` | Orchestrates the full enhancement pipeline |

### Usage

```python
from src.processor.chunk_enhancer import EnhancedChunkProcessor

processor = EnhancedChunkProcessor(
    chunks_json_path="output/whisper_chunks.json",
    frame_metadata_json_path="output/frame_metadata.json",
    frames_dir="output/extracted_frames",
    video_path="input/lecture.mp4",
    video_duration=210.0,
    video_fps=29.97,
    use_llm=True  # Set False to skip LLM descriptions
)

chunks, frames, chunks_path, frames_path = processor.process_all(
    context="Machine Learning Lecture",
    output_chunks_path="output/enhanced_chunks.json",
    output_frames_path="output/enhanced_frame_metadata.json"
)
```

### Pipeline Steps

1. Load chunk JSON and frame metadata JSON
2. Generate LLM description for each chunk (if `use_llm=True`)
3. Build uniform metadata for each frame
4. Associate frames ↔ chunks by timestamp
5. Save enhanced chunks and frame metadata

**Environment**: Requires `OPENAI_API_KEY` env var for LLM descriptions.

---

## Document Text Chunking Updates

`src/chunking/chunker.py` — the `chunk_document()` method now includes uniform metadata fields in every document text chunk:

| New Field | Value |
|-----------|-------|
| `chunk_name` | `"{doc_id}_chunk_{i}"` |
| `original_file` | From `source` or `document['original_file']` |
| `original_file_format` | Auto-detected from file extension |
| `current_format` | `"text"` |
| `uploaded_timestamp` | From document or current time |
| `content_type` | `"document_text"` |
| `uniform_metadata_version` | `"1.0"` |

This ensures **all** chunks (transcript and document) share the same metadata schema for downstream retrieval and filtering.

---

## Backward Compatibility

| Component | Status | Notes |
|-----------|--------|-------|
| `pipeline.py` | ✅ Untouched | Imports `MediaProcessor`, `MediaProcessorConfig` via wrapper |
| `unified_rag_pipeline.py` | ✅ Untouched | Imports `MediaProcessorConfig` via wrapper |
| `consolidator.py` | ✅ Untouched | No media processing changes |
| `normalizer.py` | ✅ Untouched | No changes needed |
| `document_processor.py` | ✅ Untouched | No changes needed |
| CLI `--no-gpu` flag | ✅ Works | `use_gpu=False` → sets `device="cpu"` via `__post_init__` |
| Stats dict keys | ✅ Compatible | All original keys preserved + new `chunks_created` |
| `.md` transcript | ✅ New | Preferred as `transcript_path` for Stage 3 |
| Retrieval modules | ✅ Untouched | No changes |
| Frontend / Terraform | ✅ Untouched | No changes |

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/processor/media_processor.py` | **Replaced** | Now a thin wrapper re-exporting from `media_processor_enhanced.py` |
| `src/processor/media_processor_enhanced.py` | **Updated** | Added backward-compat config, uniform metadata, `.md` export, frame-chunk association, context manager |
| `src/processor/chunk_enhancer.py` | **New** | LLM descriptions, frame metadata builder, enhanced chunk processor |
| `src/processor/__init__.py` | **Updated** | Added exports for `ChunkEnhancement`, `FrameMetadata`, `ChunkDescriptionGenerator`, `FrameMetadataBuilder`, `EnhancedChunkProcessor` |
| `src/chunking/chunker.py` | **Updated** | Added uniform metadata fields to `chunk_document()` output |
| `MEDIA_PROCESSING_ENHANCEMENTS.md` | **New** | This documentation file |

---

## Dependencies

New **optional** dependencies (gracefully degraded if missing):

| Package | Used By | Purpose |
|---------|---------|---------|
| `imagehash` | `FrameDeduplicator` | Perceptual frame hashing |
| `scipy` | `AudioNoiseReducer` | Butterworth filter |
| `librosa` | `AudioNoiseReducer` | Audio loading |
| `soundfile` | `AudioNoiseReducer` | Filtered audio saving |
| `openai` | `ChunkDescriptionGenerator` | LLM descriptions |
| `python-dotenv` | `chunk_enhancer.py` | Environment variable loading |

All dependencies are optional — the system falls back gracefully if they are not installed.

---

*End of Media Processing Enhancements Documentation*
