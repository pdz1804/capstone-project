# Complete 7-Step Video RAG Pipeline Documentation

## Overview

Both `run_full_pipeline.py` and `streamlit_app.py` now execute the **complete 7-step pipeline** for processing videos into a searchable RAG (Retrieval-Augmented Generation) system.

## Pipeline Steps

### Step 1: Audio Extraction + Noise Reduction
**Module**: `media_processor_enhanced.py` → `MediaProcessor`

- Extracts audio from video files
- Applies noise reduction:
  - Silence trimming
  - High-pass filter (removes low-frequency noise)
- Outputs: Clean audio file in `output/audio/`

### Step 2: Whisper Transcription
**Module**: `media_processor_enhanced.py` → `MediaProcessor`

- Transcribes audio using OpenAI Whisper
- Includes word-level timestamps
- Quality thresholds:
  - No speech probability < 0.6
  - Average logprob > -1.0
- Outputs: Full transcript JSON with timestamps in `output/transcripts/`

### Step 3: Token-Aware Chunking
**Module**: `media_processor_enhanced.py` → `MediaProcessor`

- Splits transcript into semantic chunks
- Maximum 100 tokens per chunk (configurable)
- Preserves sentence boundaries
- Each chunk includes:
  - `text`: Chunk content
  - `token_count`: Number of tokens
  - `start_time`, `end_time`: Temporal boundaries
  - `segment_indices`: Links to original transcript segments
- Outputs: Chunks JSON in `output/transcript_chunks/`

### Step 4: Frame Extraction + Deduplication
**Module**: `media_processor_enhanced.py` → `MediaProcessor`

- Extracts frames at configurable FPS (default: 1 fps)
- Deduplication using perceptual hashing (pHash)
- Similarity threshold: 0.95
- Frame metadata includes:
  - Timestamp
  - Frame number
  - Perceptual hash
  - File path
- Outputs: 
  - Frames: `output/extracted_frames/`
  - Metadata: `output/media_metadata/*_frame_metadata.json`

### Step 5: LLM Chunk Description Generation ⭐
**Module**: `chunk_enhancer.py` → `EnhancedChunkProcessor`

**REQUIRES**: `OPENAI_API_KEY` environment variable

This step adds AI-generated descriptions to each chunk:

```json
{
  "chunk_index": 0,
  "text": "Original transcript text...",
  "text_description": "AI-generated summary: This segment introduces the concept of Naive Bayes classifier...",
  "token_count": 95,
  "start_time": 0.0,
  "end_time": 15.2,
  "associated_frames": [
    {
      "timestamp": 2.5,
      "frame_number": 75,
      "frame_path": "output/extracted_frames/frame_0075.jpg"
    }
  ]
}
```

**Features**:
- Uses OpenAI GPT-4 for high-quality descriptions
- Associates relevant frames with each chunk by timestamp
- Gracefully skips if API key not available (logs warning)

**Outputs**: 
- `*_enhanced_chunks.json` in `output/transcript_chunks/`
- `*_enhanced_frame_metadata.json` in `output/media_metadata/`

### Step 6: RAG Indexing
**Module**: `video_rag_integration.py` → `VideoRAGPipeline`

Creates searchable index from enhanced chunks:

**Retrieval Methods**:
1. **BM25** (`SimpleBM25Retriever`): Keyword-based search
2. **Dense** (`SimpleDenseRetriever`): Semantic embeddings using sentence-transformers
3. **Hybrid** (default): Combines BM25 + Dense (alpha=0.5)

**Index Structure**:
```
output/rag_index/
├── retriever.pkl           # Serialized retriever
├── chunks_metadata.json    # Chunk information
└── document_index.json     # Document mappings
```

**What Gets Indexed**:
- Chunk text content
- LLM descriptions (if available)
- Video metadata (filename, duration, fps)
- Frame associations

**Outputs**: RAG index in `output/rag_index/`

### Step 7: Semantic Search Capability
**Module**: `video_rag_integration.py` → `VideoRAGPipeline.retrieve()`

Enables semantic queries over video content:

```python
# Example usage
rag_pipeline = VideoRAGPipeline.load_from_index("output/rag_index")
results = rag_pipeline.retrieve(
    query="What is naive bayes classifier?",
    top_k=5,
    include_frames=True
)

# Results include:
for result in results:
    print(f"Score: {result['score']}")
    print(f"Text: {result['text']}")
    print(f"Description: {result.get('text_description', 'N/A')}")
    print(f"Video: {result['video_metadata']['filename']}")
    print(f"Timestamp: {result['start_time']}-{result['end_time']}")
    print(f"Frames: {len(result.get('frames', []))}")
```

**Search Features**:
- Hybrid retrieval (keyword + semantic)
- Cross-encoder reranking (optional)
- Frame retrieval by timestamp
- Video metadata context

## Output Structure

```
output/
├── audio/                              # Step 1: Clean audio files
│   └── video_name.wav
├── transcripts/                        # Step 2: Whisper transcripts
│   └── video_name_transcript.json
├── transcript_chunks/                  # Steps 3 & 5
│   ├── video_name_chunks.json          # Basic chunks (Step 3)
│   └── video_name_enhanced_chunks.json # With LLM descriptions (Step 5)
├── extracted_frames/                   # Step 4: Frame images
│   ├── frame_0001.jpg
│   ├── frame_0002.jpg
│   └── ...
├── media_metadata/                     # Steps 4 & 5
│   ├── video_name_metadata.json        # Video info
│   ├── video_name_frame_metadata.json  # Frame info
│   └── video_name_enhanced_frame_metadata.json  # Enhanced frame info
└── rag_index/                          # Step 6: Searchable index
    ├── retriever.pkl
    ├── chunks_metadata.json
    └── document_index.json
```

## Running the Pipeline

### Option 1: Batch Processing (`run_full_pipeline.py`)

```bash
# With OpenAI API key (full 7-step pipeline)
export OPENAI_API_KEY=sk-your-key-here
python run_full_pipeline.py

# Without API key (Steps 1-4, 6-7 only, Step 5 skipped)
python run_full_pipeline.py
```

**Process**:
1. Scans `data/` directory for video/audio files
2. Processes all files through complete pipeline
3. Logs progress and statistics
4. Creates RAG index for all processed videos

**Output**: Console logs with detailed progress

### Option 2: Interactive UI (`streamlit_app.py`)

```bash
# With OpenAI API key (full 7-step pipeline)
export OPENAI_API_KEY=sk-your-key-here
streamlit run streamlit_app.py

# Without API key (Steps 1-4, 6-7 only)
streamlit run streamlit_app.py
```

**Features**:
- Upload videos via web interface
- Real-time progress tracking
- View results:
  - Transcripts with timestamps
  - Chunks with descriptions
  - Extracted frames
  - Metadata
- Search functionality (if RAG index exists)

## Environment Variables

See [.env.example](.env.example) for complete configuration options.

**Required**:
- None (pipeline runs without any env vars)

**Optional**:
- `OPENAI_API_KEY`: Enables LLM descriptions (Step 5)
- `OUTPUT_DIR`: Custom output directory
- `MAX_CHUNK_TOKENS`: Chunk size (default: 100)
- `FRAME_EXTRACTION_FPS`: Frames per second (default: 1.0)
- `WHISPER_MODEL`: Model size (default: base)

## Pipeline Behavior Without API Key

If `OPENAI_API_KEY` is not set:

✅ **Still Runs**:
- Step 1: Audio extraction + noise reduction
- Step 2: Whisper transcription
- Step 3: Token-aware chunking
- Step 4: Frame extraction + deduplication
- Step 6: RAG indexing (using chunk text only)
- Step 7: Semantic search (works but without LLM descriptions)

⚠️ **Skipped**:
- Step 5: LLM description generation

**Result**: You get a functional RAG system, but chunks won't have `text_description` field.

## Key Differences Between Scripts

| Feature | `run_full_pipeline.py` | `streamlit_app.py` |
|---------|------------------------|-------------------|
| **Interface** | Command-line batch processing | Web UI with upload |
| **Input** | Scans `data/` directory | User uploads files |
| **Progress** | Console logs | Real-time progress bar |
| **Results** | Saved to `output/` | Saved + displayed in UI |
| **Search** | Via Python API | Via web interface (planned) |
| **Use Case** | Bulk processing, automation | Interactive exploration |

## Verifying Complete Pipeline

### Check 1: Enhanced Chunks Have LLM Descriptions

```bash
# Should contain "text_description" field in each chunk
cat output/transcript_chunks/video_name_enhanced_chunks.json
```

Expected structure:
```json
{
  "metadata": {...},
  "chunks": [
    {
      "chunk_index": 0,
      "text": "...",
      "text_description": "AI-generated description here",  // ← Should exist
      "token_count": 95,
      "associated_frames": [...]
    }
  ]
}
```

### Check 2: RAG Index Exists

```bash
# Should have retriever and metadata files
ls -la output/rag_index/
```

Expected files:
- `retriever.pkl`: Serialized search index
- `chunks_metadata.json`: Chunk information
- `document_index.json`: Document mappings

### Check 3: Test Search Functionality

```python
from video_rag_integration import VideoRAGPipeline

# Load index
rag = VideoRAGPipeline.load_from_index("output/rag_index")

# Search
results = rag.retrieve("naive bayes classifier", top_k=3)

# Should return relevant chunks with scores
for r in results:
    print(f"{r['score']:.3f}: {r['text'][:100]}...")
```

## Troubleshooting

### Issue: No `text_description` field in chunks

**Cause**: `OPENAI_API_KEY` not set

**Solution**:
```bash
export OPENAI_API_KEY=sk-your-key-here
python run_full_pipeline.py
```

### Issue: RAG indexing fails

**Cause**: Missing dependencies

**Solution**:
```bash
pip install sentence-transformers rank-bm25 scikit-learn
```

### Issue: Pipeline stops at Step 4

**Cause**: Import errors for `chunk_enhancer` or `video_rag_integration`

**Solution**: Check all files exist:
- `chunk_enhancer.py`
- `video_rag_integration.py`
- `rag_retrievers.py`

## Performance Notes

**Processing Time** (per video minute):
- Steps 1-4: ~1-2 minutes
- Step 5: ~30 seconds (depends on OpenAI API)
- Step 6: ~10-30 seconds (depends on chunk count)

**Disk Space**:
- Audio: ~10 MB per minute
- Frames: ~1-5 MB per minute (at 1 fps)
- Index: ~1-5 MB per video

**Recommended Hardware**:
- CPU: 4+ cores
- RAM: 8+ GB
- GPU: Optional (speeds up Whisper if available)

## What's Next?

The pipeline now produces:
1. ✅ Complete transcripts with timestamps
2. ✅ Semantically meaningful chunks
3. ✅ Deduplicated frames
4. ✅ LLM-generated descriptions (if API key provided)
5. ✅ Searchable RAG index

**Possible Enhancements**:
- Add search UI to Streamlit app
- Implement multi-video search
- Add chunk relevance scoring
- Support video-to-video similarity
- Add frame-based visual search
- Export to various formats (PDF, JSON, CSV)

## Summary

🎉 **Both scripts now run the COMPLETE 7-STEP PIPELINE** including:
- Media processing (Steps 1-4)
- LLM chunk enhancement (Step 5) - requires API key
- RAG indexing (Step 6)
- Semantic search capability (Step 7)

The pipeline is **gracefully degradable**: it runs all critical steps even without `OPENAI_API_KEY`, simply skipping the LLM description generation while maintaining full functionality for Steps 1-4 and 6-7.
