# Video/Audio RAG Pipeline

A complete 7-step pipeline for processing videos/audio into a searchable Retrieval-Augmented Generation (RAG) system with semantic search capabilities.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up OpenAI API (Optional but Recommended)
For LLM-generated chunk descriptions, set your OpenAI API key:
```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "sk-your-key-here"

# Or create .env file
echo 'OPENAI_API_KEY=sk-your-key-here' > .env
```

### 3. Run the Pipeline

#### Option A: Batch Processing (Process all videos in `data/` folder)
```bash
python run_full_pipeline.py
```

#### Option B: Interactive Web UI (Upload and process one video)
```bash
streamlit run streamlit_app.py
```

## Pipeline Overview

The pipeline automates 7 steps:

1. **Audio Extraction + Noise Reduction** - Extract clean audio from video
2. **Whisper Transcription** - Convert audio to text with word-level timestamps
3. **Token-Aware Chunking** - Split transcript into semantic chunks (max 100 tokens)
4. **Frame Extraction** - Extract and deduplicate frames with perceptual hashing
5. **LLM Enhancement** - Add AI descriptions to chunks (requires OpenAI API key)
6. **RAG Indexing** - Create searchable index with hybrid retrieval (BM25 + Dense)
7. **Semantic Search** - Query video content by meaning, not just keywords

## Input/Output

**Input**: Place video/audio files in `data/` folder (supports: MP4, AVI, MOV, MKV, WAV, MP3, M4A)

**Output** (`output/` folder):
```
output/
├── audio/                              # Clean extracted audio
├── transcripts/                        # Full transcripts (JSON, TXT, SRT, VTT)
├── transcript_chunks/                  # Chunks ± LLM descriptions
├── extracted_frames/                   # Deduplicated frames
├── media_metadata/                     # Frame and video metadata
└── rag_index/                          # Searchable index
```

## Features

✅ **Works Without API Key** - Runs Steps 1-4, 6-7 (skips Step 5 LLM descriptions)  
✅ **Graceful Degradation** - Pipeline continues if LLM step fails  
✅ **Frame-Chunk Mapping** - Associates frames with transcript chunks by timestamp  
✅ **Hybrid Search** - Keyword (BM25) + Semantic (Dense embeddings)  
✅ **Deduplication** - Removes duplicate frames using perceptual hashing  
✅ **Multiple Formats** - Exports transcripts as JSON, TXT, SRT, VTT  

## Configuration

Edit `.env` file or set environment variables:

```
# OpenAI API Key (required for Step 5 - LLM descriptions)
OPENAI_API_KEY=sk-your-key-here

# Pipeline Configuration
MAX_CHUNK_TOKENS=100              # Maximum tokens per chunk
CHUNK_OVERLAP_TOKENS=10           # Overlap for context continuity
WHISPER_MODEL=base                # tiny, base, small, medium, large
FRAME_EXTRACTION_FPS=1.0          # Frames per second
FRAME_DEDUP_THRESHOLD=0.95        # Perceptual hash similarity

# Directories (relative to this folder)
OUTPUT_DIR=output
```

See `.env.example` for all available options.

## Usage Examples

### Example 1: Process a Video with Full Pipeline
```bash
python run_full_pipeline.py
```
Results saved to `output/` with all 7 steps completed.

### Example 2: Search Video Content Programmatically
```python
from video_rag_integration import VideoRAGPipeline

# Load the RAG index
rag = VideoRAGPipeline.load_from_index("output/rag_index")

# Search for relevant chunks
results = rag.retrieve(
    query="What is naive bayes classifier?",
    top_k=5,
    include_frames=True
)

# Results include text, timestamps, video metadata, and frames
for result in results:
    print(f"Score: {result['score']:.1%}")
    print(f"Text: {result['text']}")
    print(f"Time: {result['start_time']:.1f}s - {result['end_time']:.1f}s")
    print(f"Frames: {len(result.get('frames', []))}\n")
```

### Example 3: Interactive Web Search
```bash
streamlit run streamlit_app.py
```
1. Upload a video
2. Wait for processing
3. Click "Results" tab
4. Enter search query
5. View results with timestamps, descriptions, and frame images

## Verifying the Pipeline

Check that enhanced chunks include LLM descriptions:
```bash
# Should show "text_description" field in each chunk
cat output/transcript_chunks/video_name_enhanced_chunks.json
```

Test search functionality:
```python
from video_rag_integration import VideoRAGPipeline
rag = VideoRAGPipeline.load_from_index("output/rag_index")
results = rag.retrieve("your query", top_k=3)
print(f"Found {len(results)} results")
```

## Performance

**Processing Time per Video Minute**:
- Steps 1-4 (Media processing): ~1-2 minutes
- Step 5 (LLM descriptions): ~30 seconds (depends on API)
- Steps 6-7 (Indexing + search setup): ~10-30 seconds

**Disk Space per Video**:
- Audio: ~10 MB/minute
- Frames: ~1-5 MB/minute (at 1 fps)
- Index: ~1-5 MB

**Recommended Hardware**:
- CPU: 4+ cores
- RAM: 8+ GB
- GPU: Optional (speeds up Whisper)

## Troubleshooting

**Issue: "No module named 'openai'"**  
→ Run: `pip install -r requirements.txt`

**Issue: "OPENAI_API_KEY not found"**  
→ Create `.env` file with your key, or set environment variable

**Issue: No frame images in output**  
→ Check `output/extracted_frames/` folder exists with JPEG files

**Issue: Search results are empty or irrelevant**  
→ Ensure RAG index exists: `ls output/rag_index/`

## File Structure

```
Phase_2_PDZ_001/
├── README.md                               # This file
├── COMPLETE_PIPELINE_DOCUMENTATION.md     # Detailed pipeline docs
├── requirements.txt                        # Python dependencies
├── .env.example                            # Configuration template
│
├── Media Processing
│   ├── media_processor_enhanced.py         # Core audio/video processing
│   ├── chunking_utils.py                   # Chunking utilities
│   └── chunk_enhancer.py                   # LLM enhancement
│
├── RAG & Search
│   ├── rag_retrievers.py                   # BM25, Dense, Hybrid retrieval
│   └── video_rag_integration.py            # RAG pipeline orchestration
│
├── Entry Points
│   ├── run_full_pipeline.py                # Batch processing script
│   └── streamlit_app.py                    # Web UI
│
├── data/                                   # Input folder (place videos here)
├── output/                                 # Results folder (auto-created)
├── input/                                  # Temp folder
└── uploads/                                # Temp uploads
```

## Documentation

- **This File (README.md)**: Quick start and how to run
- **COMPLETE_PIPELINE_DOCUMENTATION.md**: Detailed technical documentation of all 7 steps, output structure, and advanced usage

## Support

For detailed technical documentation, see [COMPLETE_PIPELINE_DOCUMENTATION.md](COMPLETE_PIPELINE_DOCUMENTATION.md).

---

**Status**: ✅ Production Ready  
**Last Updated**: February 2026
