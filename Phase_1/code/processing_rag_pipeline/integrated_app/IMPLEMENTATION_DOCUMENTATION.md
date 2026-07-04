# Unified RAG Pipeline - Complete Implementation Documentation

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: Document Processing Pipeline](#phase-1-document-processing-pipeline)
3. [Phase 2: Text Chunking](#phase-2-text-chunking)
4. [Phase 3: Text-Based Retrieval](#phase-3-text-based-retrieval)
5. [Phase 4: Image-Based Retrieval](#phase-4-image-based-retrieval)
6. [Phase 5: Reranking](#phase-5-reranking)
7. [Phase 6: Answer Generation](#phase-6-answer-generation)
8. [Phase 7: Evaluation & Benchmarking](#phase-7-evaluation--benchmarking)
9. [Phase 8: Web Interface](#phase-8-web-interface)
10. [Architecture & Integration](#architecture--integration)
11. [Configuration System](#configuration-system)
12. [Performance Optimization](#performance-optimization)

---

## Overview

The Unified RAG Pipeline is a comprehensive, production-ready system that combines **document processing** and **information retrieval** into a complete RAG (Retrieval-Augmented Generation) workflow. It processes documents of any format, extracts structured content, builds multiple retrieval indexes, and provides answer generation with citations.

### Key Features

- **Multi-format Document Processing**: DOCX, PPTX, PDF, HTML, Images, Excel, CSV, Video, Audio
- **Multiple Retrieval Strategies**: BM25 (sparse), Dense (semantic), Hybrid (combined)
- **Image-Based Retrieval**: ColQwen vision-language model for visual document understanding
- **Reranking**: Cross-encoder models for improved retrieval quality
- **Answer Generation**: GPT-4o-mini with proper citation formatting
- **Evaluation Metrics**: nDCG, Recall, MRR, MAP
- **Web Interface**: Modern React frontend with FastAPI backend

### Technology Stack

- **Document Processing**: Docling, LibreOffice, FFmpeg, Whisper
- **Retrieval**: BM25, Sentence Transformers, FAISS, ColQwen
- **Reranking**: BGE-Reranker, MiniLM Cross-Encoder
- **Generation**: OpenAI GPT-4o-mini, Azure OpenAI, Ollama
- **Frontend**: React, Vite, Tailwind CSS
- **Backend**: FastAPI, Python 3.9+

---

## Phase 1: Document Processing Pipeline

### Overview

The document processing pipeline transforms raw documents of any format into RAG-ready structured formats. It consists of four sequential stages:

1. **Normalization**: Convert formats to PDF/Markdown
2. **Media Processing**: Extract audio, transcribe, extract frames
3. **Document Processing**: Deep analysis with Docling (OCR, VLM, table extraction)
4. **Consolidation**: Unify outputs into consistent RAG-ready structure

### Stage 1: Normalization

**Location**: `src/processor/normalizer.py`

**Purpose**: Convert various document formats into standardized PDF and Markdown formats for downstream processing.

**Supported Formats**:
- **DOCX/PPTX** → PDF (via LibreOffice)
- **HTML** → PDF (via LibreOffice)
- **Images** → PDF (for image-based RAG)
- **TXT** → Markdown
- **Excel/CSV** → Markdown tables

**Key Implementation Details**:

```python
class DocumentNormalizer:
    def normalize_batch(self) -> Dict:
        """
        Process all files in input directory:
        1. DOCX/PPTX/HTML → PDF (normalized_pdfs/)
        2. Images → PDF (normalized_pdfs/)
        3. TXT → Markdown (normalized_markdown/)
        4. Copy originals to original_files/ (for Docling)
        """
```

**Output Structure**:
```
stage1_normalized/
├── normalized_pdfs/          # PDFs for image-based RAG
│   ├── document1.pdf
│   └── document2.pdf
├── normalized_markdown/       # Markdown for text-based RAG
│   └── text_file.md
└── original_files/           # Originals preserved for Docling
    ├── document1.docx
    └── document2.pptx
```

**Configuration Options**:
- `generate_pdf`: Enable PDF generation (default: True)
- `generate_markdown`: Enable Markdown generation (default: True)
- `image_to_pdf`: Convert standalone images to PDF (default: True)
- `image_quality`: JPEG quality 1-100 (default: 95)
- `excel_to_markdown`: Convert Excel to Markdown tables (default: True)
- `csv_to_markdown`: Convert CSV to Markdown tables (default: True)

**Dependencies**:
- LibreOffice (for DOCX/PPTX/HTML conversion)
- Poppler (for PDF utilities)
- Pillow (for image processing)

### Stage 2: Media Processing

**Location**: `src/processor/media_processor.py`

**Purpose**: Process video and audio files to extract transcripts and frames for multimodal RAG.

**Supported Formats**:
- **Video**: MP4, AVI, MOV, MKV, etc.
- **Audio**: MP3, WAV, FLAC, M4A, etc.

**Key Features**:
1. **Audio Extraction**: Extract audio track from video files
2. **Transcription**: Convert audio to text using Whisper ASR
3. **Frame Extraction**: Extract video frames for image retrieval (optional)
4. **Multiple Export Formats**: JSON, SRT, VTT, TXT, Markdown

**Key Implementation Details**:

```python
class MediaProcessor:
    def process_batch(self) -> Dict:
        """
        For each video/audio file:
        1. Extract audio (if video)
        2. Transcribe using Whisper
        3. Export transcripts in multiple formats
        4. Extract frames (if enabled)
        """
```

**Output Structure**:
```
stage2_media_processed/
├── transcripts/
│   ├── video1.json           # Timestamped transcript
│   ├── video1.srt            # Subtitle format
│   ├── video1.vtt            # WebVTT format
│   ├── video1.txt            # Plain text
│   └── video1.md             # Markdown format
├── extracted_audio/
│   └── video1.wav
├── extracted_frames/
│   └── video1/
│       ├── frame_000.png
│       └── frame_100.png
└── media_metadata/
    └── media_processing_stats.json
```

**Configuration Options**:
- `extract_audio`: Extract audio from video (default: True)
- `enable_transcription`: Enable Whisper transcription (default: True)
- `asr_model`: Whisper model size - "tiny", "base", "small", "medium", "large", "large-v3" (default: "base")
- `asr_language`: Language code or null for auto-detect (default: null)
- `extract_frames`: Extract video frames (default: True)
- `frame_interval`: Extract every Nth frame (default: 100)
- `chunk_duration`: Seconds per chunk for long audio (default: 30)

**Dependencies**:
- FFmpeg (for audio/video processing)
- Whisper (OpenAI's speech recognition)
- PyTorch (for Whisper models)

**Performance Notes**:
- GPU acceleration available for Whisper transcription
- Large models ("large", "large-v3") provide better accuracy but slower processing
- Frame extraction can be disabled for faster processing

### Stage 3: Document Processing (Docling)

**Location**: `src/processor/document_processor.py`

**Purpose**: Deep document analysis using IBM Docling for OCR, VLM-based image understanding, table extraction, and structured content extraction.

**Key Features**:
1. **OCR**: Extract text from scanned documents and images
2. **VLM Processing**: Vision Language Model (SmolVLM-256M) for image descriptions
3. **Table Extraction**: Extract tables with structure preservation
4. **Image Extraction**: Extract embedded images from documents
5. **Smart Deduplication**: Avoid processing same file twice

**Smart Deduplication Logic**:

The pipeline implements intelligent deduplication to avoid processing the same document multiple times:

1. **Priority Order**:
   - Normalized PDFs (highest priority - best quality from conversions)
   - Normalized Markdown files
   - Original files NOT already converted
   - Transcript files from media processing

2. **Deduplication Process**:
   ```python
   # Track processed base names
   processed_basenames = set()
   
   # Step 1: Process normalized PDFs first
   for pdf_file in normalized_pdfs:
       processed_basenames.add(pdf_file.stem)
   
   # Step 2: Process normalized Markdown
   for md_file in normalized_markdown:
       processed_basenames.add(md_file.stem)
   
   # Step 3: Only process originals NOT in processed_basenames
   unique_originals = [f for f in originals if f.stem not in processed_basenames]
   ```

**Key Implementation Details**:

```python
class MultimodalDocumentProcessor:
    def process_batch(self) -> Dict:
        """
        For each document:
        1. Load with Docling DocumentConverter
        2. Extract text, images, tables
        3. Run OCR if needed
        4. Run VLM for image descriptions (if enabled)
        5. Export markdown + metadata + extracted assets
        """
```

**Output Structure**:
```
stage3_document_processed/
├── document1/
│   ├── document1.md              # Main markdown content
│   ├── document1_metadata.json    # Document metadata
│   ├── image_000.png             # Extracted images
│   ├── image_001.png
│   ├── table_000.csv             # Extracted tables
│   ├── table_000.md              # Table as markdown
│   └── ...
└── document2/
    └── ...
```

**Configuration Options**:
- `use_gpu`: Enable GPU acceleration (default: True)
- `enable_ocr`: Enable OCR for scanned documents (default: True)
- `enable_vlm`: Enable Vision Language Model for image descriptions (default: True)
- `ocr_engine`: "rapidocr", "tesseract", "easyocr" (default: "rapidocr")
- `vlm_model`: "granite_docling" or custom (default: "granite_docling")
- `export_markdown`: Export markdown files (default: True)
- `export_images`: Export extracted images (default: True)
- `export_tables`: Export extracted tables (default: True)

**Dependencies**:
- Docling (IBM's document processing library)
- Tesseract OCR (optional, for OCR)
- PyTorch (for VLM models)
- CUDA (for GPU acceleration)

**Performance Modes**:

1. **Fast Mode** (`--fast-mode`):
   - Disables VLM processing (3-5x faster)
   - Disables image/table extraction
   - Still extracts all text content
   - Best for development/testing

2. **Balanced Mode** (default):
   - VLM enabled for image descriptions
   - Full extraction (text + images + tables)
   - Best quality for production

3. **GPU Acceleration**:
   - CUDA required for VLM models
   - Significant speedup for large documents
   - Falls back to CPU if GPU unavailable

### Stage 4: Consolidation

**Location**: `src/processor/consolidator.py`

**Purpose**: Consolidate outputs from all previous stages into a unified RAG-ready structure.

**Key Features**:
1. **Unified Structure**: Consistent format for all document types
2. **PDF Preservation**: Keep PDFs for image-based RAG
3. **Markdown Consolidation**: Combine all text content into markdown
4. **Additional Assets**: Preserve extracted images and tables

**Key Implementation Details**:

```python
class Stage4Consolidator:
    def consolidate(self) -> Dict:
        """
        For each processed document:
        1. Find PDF from stage1 (if available)
        2. Find Markdown from stage3 (Docling output)
        3. Copy additional assets (images, tables)
        4. Create unified folder structure
        """
```

**Output Structure**:
```
stage4_rag_ready/
├── document1/
│   ├── document1.pdf              # For image-based RAG (optional)
│   ├── document1.md                # For text-based RAG (required)
│   └── docling_additional/         # Optional supplementary files
│       ├── image_000.png
│       ├── table_000.csv
│       └── ...
└── document2/
    └── ...
```

**RAG-Ready Format Requirements**:

Each document folder must contain:
- **file.md** (required): Main markdown content for text-based retrieval
- **file.pdf** (optional): PDF for image-based retrieval (ColQwen)
- **docling_additional/** (optional): Images, tables, metadata

**Statistics Tracking**:
- Total documents consolidated
- Documents with PDF
- Documents with Markdown
- Documents with additional assets

### Pipeline Orchestration

**Location**: `src/processor/pipeline.py`

**Main Class**: `DocumentProcessingPipeline`

**Execution Flow**:

```python
pipeline = DocumentProcessingPipeline(input_dir, output_dir, config)
stats = pipeline.run()

# Stages executed:
# 1. Normalization (if enabled)
# 2. Media Processing (if enabled)
# 3. Document Processing (if enabled)
# 4. Consolidation (always executed)
```

**Caching System**:

The pipeline implements a processing cache to skip already-processed files:

```python
# Cache file: .processing_cache.json
{
    "document1.docx": {
        "hash": "md5_hash",
        "status": "success",
        "timestamp": "2025-01-01T00:00:00"
    }
}
```

**Cache Logic**:
1. Check file hash against cache
2. Verify stage4 output exists
3. Skip processing if file unchanged and successfully processed

**Error Handling**:
- Individual file failures don't stop the pipeline
- Errors logged with file path and error message
- Failed files tracked in statistics

---

## Phase 2: Text Chunking

### Overview

Text chunking splits large documents into smaller, manageable pieces for better retrieval precision. The system uses **Recursive Character Text Splitting** to preserve semantic meaning.

**Location**: `src/chunking/chunker.py`

### Chunking Strategy

**Hierarchical Splitting**:

The chunker splits text in order of priority:

1. **Paragraphs** (`\n\n`) - Preserves document structure
2. **Lines** (`\n`) - Maintains line-level context
3. **Sentences** (`. `) - Keeps sentence boundaries
4. **Words** (` `) - Preserves word boundaries
5. **Characters** - Final fallback for very long words

**Key Implementation**:

```python
class TextChunker:
    def chunk_document(self, text: str) -> List[Dict]:
        """
        Recursively split text:
        1. Try splitting by paragraphs
        2. If chunks too large, split by lines
        3. If still too large, split by sentences
        4. Continue until chunks fit size requirements
        5. Add overlap between chunks
        """
```

### Configuration

**Default Settings**:
- `chunk_size`: 1000 characters
- `chunk_overlap`: 200 characters
- `min_chunk_size`: 50 characters (skip tiny chunks)
- `separators`: `["\n\n", "\n", ". ", " ", ""]`

**Recommended Configurations**:

| Use Case | Chunk Size | Overlap | Notes |
|----------|------------|---------|-------|
| Precise Q&A | 500 | 100 | More specific retrieval |
| **General RAG** | **1000** | **200** | **Default, balanced** |
| Long context | 2000 | 400 | More context per chunk |
| Full documents | N/A | N/A | Use `--no-chunking` |

### Chunk Metadata

Each chunk includes:

```python
{
    "id": "document1_chunk_0",
    "text": "chunk content...",
    "source": "document1.md",
    "chunk_index": 0,
    "start_char": 0,
    "end_char": 1000,
    "metadata": {
        "document_id": "document1",
        "chunk_number": 0,
        "total_chunks": 15
    }
}
```

### Integration with Retrieval

Chunks are created during retrieval index building:

```python
# In rag_retrievers.py
chunker = TextChunker(config=ChunkingConfig(
    chunk_size=1000,
    chunk_overlap=200
))

chunks = chunker.chunk_documents(documents)
# Then index chunks instead of full documents
```

**Benefits**:
- Better retrieval precision (smaller, focused chunks)
- Overlap prevents information loss at boundaries
- Preserves document structure and context
- Configurable for different use cases

---

## Phase 3: Text-Based Retrieval

### Overview

The text-based retrieval system provides three retrieval methods: BM25 (sparse), Dense (semantic), and Hybrid (combined). All methods work on chunked documents from the processing pipeline.

**Location**: `src/retrieval/rag_retrievers.py`

### BM25 Retriever (Sparse)

**Type**: Keyword-based retrieval using TF-IDF statistics

**Model**: `rank_bm25.BM25Okapi`

**How It Works**:
1. Tokenize documents and queries
2. Calculate BM25 scores based on term frequency and inverse document frequency
3. Rank documents by relevance score

**Key Implementation**:

```python
class SimpleBM25Retriever(BaseRetriever):
    def index_documents(self, documents: List[Dict]):
        """Build BM25 index from tokenized documents"""
        self.tokenized_docs = [self._tokenize(doc['text']) for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)
    
    def search(self, query: str, top_k: int = 10):
        """Search and return top-k results"""
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        # Return top-k documents with scores
```

**Strengths**:
- Fast and memory-efficient
- Good for exact term matching
- No model loading required
- Works well for keyword queries

**Limitations**:
- Cannot handle semantic similarity
- Requires exact term matches
- Limited understanding of synonyms

**Use Cases**:
- Exact term searches
- Keyword-based queries
- Fast retrieval for large corpora

### Dense Retriever (Semantic)

**Type**: Embedding-based semantic retrieval

**Model**: `sentence-transformers/all-MiniLM-L6-v2` (default)

**How It Works**:
1. Generate embeddings for all document chunks using sentence transformer
2. Generate query embedding
3. Compute cosine similarity between query and document embeddings
4. Rank by similarity score

**Key Implementation**:

```python
class DenseRetriever(BaseRetriever):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.embeddings = None  # FAISS index
    
    def index_documents(self, documents: List[Dict]):
        """Generate embeddings and build FAISS index"""
        texts = [doc['text'] for doc in documents]
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        # Build FAISS index for fast similarity search
    
    def search(self, query: str, top_k: int = 10):
        """Search using cosine similarity"""
        query_embedding = self.model.encode([query])
        scores, indices = self.faiss_index.search(query_embedding, top_k)
        # Return top-k documents
```

**FAISS Index**:
- Uses FAISS (Facebook AI Similarity Search) for fast vector search
- GPU acceleration available
- Supports approximate nearest neighbor search for very large corpora

**Available Models**:
- `all-MiniLM-L6-v2`: Fast, 384 dimensions (default)
- `BAAI/bge-small-en-v1.5`: Better quality, 384 dimensions
- `BAAI/bge-base-en-v1.5`: Higher quality, 768 dimensions
- Custom HuggingFace models

**Strengths**:
- Understands semantic similarity
- Handles synonyms and related concepts
- Better for conceptual queries
- Works well with paraphrased queries

**Limitations**:
- Requires model loading (memory overhead)
- Slower than BM25 for indexing
- May miss exact term matches

**Use Cases**:
- Semantic search
- Conceptual queries
- Paraphrased questions
- Cross-lingual retrieval (with multilingual models)

### Hybrid Retriever

**Type**: Combination of BM25 and Dense retrieval using Reciprocal Rank Fusion (RRF)

**How It Works**:
1. Retrieve candidates from both BM25 and Dense retrievers
2. Use **130% expansion**: Retrieve `top_k * 1.3` from each retriever
3. Fuse results using Reciprocal Rank Fusion (RRF)
4. Return top-k final results

**Reciprocal Rank Fusion (RRF)**:

```python
def reciprocal_rank_fusion(bm25_results, dense_results, k=60):
    """
    RRF formula: score = sum(1 / (k + rank))
    - Lower rank (better position) = higher score
    - k is a constant (typically 60)
    """
    scores = {}
    
    # Add BM25 results
    for rank, doc_id in enumerate(bm25_results, 1):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    # Add Dense results
    for rank, doc_id in enumerate(dense_results, 1):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    # Sort by combined score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**Key Implementation**:

```python
class HybridRetriever(BaseRetriever):
    def __init__(self, bm25_retriever, dense_retriever):
        self.bm25 = bm25_retriever
        self.dense = dense_retriever
    
    def search(self, query: str, top_k: int = 10):
        """Hybrid search with RRF fusion"""
        # Expand: retrieve 130% of requested top_k
        expanded_k = int(top_k * 1.3)
        
        # Get results from both retrievers
        bm25_results = self.bm25.search(query, top_k=expanded_k)
        dense_results = self.dense.search(query, top_k=expanded_k)
        
        # Fuse using RRF
        fused_results = self._reciprocal_rank_fusion(
            bm25_results, dense_results
        )
        
        # Return top-k after fusion
        return fused_results[:top_k]
```

**Expansion Factor**:
- **130% expansion**: If requesting top-10, retrieve 13 from each retriever
- Reason: Some relevant docs may rank differently in each method
- Ensures best candidates from both methods are considered

**Result Metadata**:

Hybrid results include fusion information:

```python
{
    "id": "document1_chunk_5",
    "text": "...",
    "score": 0.045,  # RRF fused score
    "retrieval_info": {
        "bm25_rank": 3,      # Rank in BM25 results
        "dense_rank": 8,     # Rank in Dense results
        "in_both": True,     # Appeared in both methods
        "in_bm25": True,
        "in_dense": True
    }
}
```

**Strengths**:
- Combines best of both worlds
- Better recall than individual methods
- Handles both keyword and semantic queries
- More robust to query variations

**Limitations**:
- More complex than individual methods
- Requires both indexes (more memory)
- Slightly slower than individual methods

**Use Cases**:
- **Default choice** for most RAG applications
- Production systems requiring high quality
- Mixed query types (keyword + semantic)

### Index Persistence

All retrievers support saving and loading indexes:

**Save Index**:

```python
manager = create_rag_retriever(
    doc_dir="output/processing/stage4_rag_ready/",
    retriever_types=["bm25", "dense", "hybrid"],
    index_dir="output/retrieval/",
    save_index=True
)
```

**Load Index**:

```python
manager = load_rag_retriever("output/retrieval/")
# Fast startup - no re-indexing needed
```

**Index Structure**:

```
output/retrieval/
├── documents.json              # Chunked documents metadata
├── index_meta.json             # Index configuration
├── bm25/
│   └── bm25_index.pkl          # BM25 index
├── dense/
│   ├── faiss_index.bin         # FAISS vector index
│   └── dense_meta.pkl          # Embedding metadata
└── hybrid/
    ├── bm25_index.pkl          # BM25 component
    ├── faiss_index.bin         # Dense component
    └── dense_meta.pkl
```

**Index Metadata**:

```json
{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "num_chunks": 1500,
    "num_documents": 50,
    "embedding_model": "all-MiniLM-L6-v2",
    "created_at": "2025-01-01T00:00:00"
}
```

### RAG Retriever Manager

**Location**: `src/retrieval/rag_retrievers.py`

**Class**: `RAGRetrieverManager`

**Purpose**: Manages multiple retrievers and provides unified interface.

**Key Methods**:

```python
class RAGRetrieverManager:
    def search(
        self, 
        query: str, 
        retriever_type: str = "hybrid",
        top_k: int = 10,
        use_reranker: bool = False
    ) -> List[Dict]:
        """Search using specified retriever"""
    
    def get_available_retrievers(self) -> List[str]:
        """Get list of initialized retrievers"""
    
    def save_index(self, index_dir: Path):
        """Save all indexes to disk"""
    
    def load_index(self, index_dir: Path):
        """Load indexes from disk"""
```

**Factory Functions**:

```python
# Create new retriever manager
manager = create_rag_retriever(
    doc_dir="output/processing/stage4_rag_ready/",
    retriever_types=["bm25", "dense", "hybrid"],
    chunk_size=1000,
    chunk_overlap=200,
    reranker_model="bge-large"  # Optional
)

# Load existing retriever manager
manager = load_rag_retriever("output/retrieval/")
```

---

## Phase 4: Image-Based Retrieval

### Overview

Image-based retrieval uses vision-language models to understand and retrieve PDF pages based on visual content, not just text. This is essential for documents with diagrams, charts, tables, and visual layouts.

**Location**: `src/retrieval/image_retrievers.py`

**Model**: ColQwen 2.5 (Vision-Language Model)

### ColQwen Retriever

**Model**: `vidore/colqwen2-v1.0` or `vidore/colqwen2.5-v0.2`

**How It Works**:
1. Convert PDF pages to images (using pdf2image)
2. Generate embeddings for each page using ColQwen vision-language model
3. Generate query embedding (text query converted to visual understanding)
4. Compute cosine similarity between query and page embeddings
5. Return top-k most relevant pages

**Key Implementation**:

```python
class ColQwenRetriever(BaseImageRetriever):
    def __init__(
        self,
        model_name: str = "vidore/colqwen2-v1.0",
        dtype: str = "bfloat16",
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
        pdf_dpi: int = 150
    ):
        """Initialize ColQwen model with quantization options"""
    
    def index_pdfs(self, pdf_dir: Path):
        """Convert PDFs to images and generate embeddings"""
        for pdf_file in pdf_dir.glob("**/*.pdf"):
            # Convert PDF to images
            images = pdf2image.convert_from_path(
                pdf_file, dpi=self.pdf_dpi
            )
            
            # Generate embeddings for each page
            for page_num, image in enumerate(images):
                embedding = self.model.encode_image(image)
                self.index.append({
                    "source": pdf_file.name,
                    "page": page_num + 1,
                    "embedding": embedding
                })
    
    def search(self, query: str, top_k: int = 10):
        """Search using text query"""
        query_embedding = self.model.encode_text(query)
        # Compute cosine similarity
        # Return top-k pages
```

### Model Configuration

**Available Models**:
- `vidore/colqwen2-v1.0`: ColQwen 2 (compatible with older colpali-engine)
- `vidore/colqwen2.5-v0.2`: ColQwen 2.5 (requires newer colpali-engine>=0.4.0)

**Data Types**:
- `bfloat16`: Fast, less memory, best for CUDA (default)
- `float16`: Alternative to bfloat16
- `float32`: More precise, slower, required for CPU

**Quantization Options**:

1. **No Quantization** (default):
   - Memory: ~7GB VRAM
   - Speed: Fastest
   - Quality: Best

2. **4-bit Quantization**:
   - Memory: ~2.5GB VRAM
   - Speed: Slower
   - Quality: Slightly reduced
   - Requires: `bitsandbytes`

3. **8-bit Quantization**:
   - Memory: ~4GB VRAM
   - Speed: Medium
   - Quality: Good
   - Requires: `bitsandbytes`

**Configuration Example**:

```yaml
image_retrieval:
  colqwen:
    model: "vidore/colqwen2-v1.0"
    dtype: "bfloat16"
    quantization: "8bit"  # or "4bit", null
    pdf_dpi: 150
```

### PDF to Image Conversion

**DPI Settings**:
- **150 DPI** (default): Balanced quality and speed
- **200-300 DPI**: Higher quality, slower processing
- **100 DPI**: Faster, lower quality

**Impact**:
- Higher DPI = better image quality = better retrieval
- Higher DPI = more memory usage = slower processing

### Index Structure

**Output**:

```
output/image_retrieval/
├── image_index_meta.json
└── colqwen/
    ├── colqwen_index.pkl      # Page embeddings
    └── colqwen_meta.json      # Metadata
```

**Metadata**:

```json
{
    "model": "vidore/colqwen2-v1.0",
    "dtype": "bfloat16",
    "quantization": "8bit",
    "pdf_dpi": 150,
    "num_pages": 250,
    "num_pdfs": 10,
    "embedding_dim": 1024
}
```

### Search Results

**Result Format**:

```python
[
    {
        "source": "document1.pdf",
        "page": 5,
        "score": 0.892,
        "image_path": "path/to/page_5.png",  # Optional
        "text": "extracted text from page"   # Optional
    },
    ...
]
```

### Image RAG Manager

**Location**: `src/retrieval/image_retrievers.py`

**Class**: `ImageRAGManager`

**Purpose**: Manages image-based retrievers (currently ColQwen, extensible for more).

**Key Methods**:

```python
class ImageRAGManager:
    def search(
        self,
        query: str,
        retriever_type: str = "colqwen",
        top_k: int = 5
    ) -> List[Dict]:
        """Search for relevant PDF pages"""
    
    def get_available_retrievers(self) -> List[str]:
        """Get list of initialized retrievers"""
    
    def save_index(self, index_dir: Path):
        """Save index to disk"""
    
    def load_index(self, index_dir: Path, colqwen_config: Dict):
        """Load index from disk"""
```

**Factory Functions**:

```python
# Create new image retriever
manager = create_image_retriever(
    pdf_dir="output/processing/stage4_rag_ready/",
    retriever_types=["colqwen"],
    index_dir="output/image_retrieval/",
    colqwen_config={
        "model": "vidore/colqwen2-v1.0",
        "dtype": "bfloat16",
        "load_in_8bit": True,
        "pdf_dpi": 150
    }
)

# Load existing image retriever
manager = load_image_retriever(
    "output/image_retrieval/",
    colqwen_config={...}
)
```

### Use Cases

**Best For**:
- Documents with diagrams and charts
- Visual layouts and designs
- Tables and structured data
- Mixed text-image documents
- When text extraction is insufficient

**Limitations**:
- Requires GPU for reasonable performance
- Slower than text-based retrieval
- Higher memory requirements
- May not work well for pure text documents

---

## Phase 5: Reranking

### Overview

Reranking improves retrieval quality by using cross-encoder models to score all candidate documents. While initial retrieval is fast but approximate, reranking is slower but more accurate.

**Location**: Integrated in `src/retrieval/rag_retrievers.py`

### How Reranking Works

**Two-Stage Process**:

1. **Initial Retrieval**: Fast retrieval of `top_k * multiplier` candidates
2. **Reranking**: Cross-encoder scores all candidates, returns top-k

**Process Flow**:

```python
def search_with_reranking(query, top_k=10, multiplier=3):
    # Stage 1: Initial retrieval (fast)
    candidates = initial_retriever.search(query, top_k=top_k * multiplier)
    # Example: top_k=10, multiplier=3 → retrieve 30 candidates
    
    # Stage 2: Reranking (slower but accurate)
    reranker_scores = reranker.score(query, candidates)
    
    # Stage 3: Return top-k after reranking
    reranked_results = sorted(
        zip(candidates, reranker_scores),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]
    
    return reranked_results
```

### Available Rerankers

**1. BGE-Large Reranker**

- **Model**: `BAAI/bge-reranker-large`
- **Quality**: Best
- **Speed**: Slowest
- **Use Case**: Maximum retrieval quality

**2. BGE-Base Reranker**

- **Model**: `BAAI/bge-reranker-base`
- **Quality**: Good
- **Speed**: Faster than large
- **Use Case**: Balanced quality/speed

**3. MiniLM-L12 Cross-Encoder**

- **Model**: `cross-encoder/ms-marco-MiniLM-L-12-v2`
- **Quality**: Better than baseline
- **Speed**: Fastest reranker
- **Use Case**: Quick reranking with improvement

### Cross-Encoder Architecture

**How Cross-Encoders Work**:

Unlike bi-encoders (which encode query and document separately), cross-encoders:
1. Take query and document together as input
2. Use attention mechanism to understand interaction
3. Output relevance score directly

**Advantages**:
- Better understanding of query-document interaction
- More accurate relevance scoring
- Handles complex relationships

**Disadvantages**:
- Slower (must process each query-document pair)
- Cannot pre-compute document embeddings
- More expensive computationally

### Implementation

**Reranker Integration**:

```python
class RAGRetrieverManager:
    def __init__(self, ..., reranker_model: Optional[str] = None):
        if reranker_model:
            self.reranker = self._load_reranker(reranker_model)
        else:
            self.reranker = None
    
    def search(
        self,
        query: str,
        retriever_type: str = "hybrid",
        top_k: int = 10,
        use_reranker: bool = False
    ):
        # Initial retrieval
        results = self._initial_search(query, retriever_type, top_k)
        
        # Rerank if enabled
        if use_reranker and self.reranker:
            results = self._rerank(query, results, top_k)
        
        return results
    
    def _rerank(self, query: str, candidates: List[Dict], top_k: int):
        """Rerank candidates using cross-encoder"""
        # Prepare query-document pairs
        pairs = [(query, doc['text']) for doc in candidates]
        
        # Score all pairs
        scores = self.reranker.predict(pairs)
        
        # Sort by score and return top-k
        reranked = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        return [doc for doc, score in reranked]
```

### Configuration

**Enable Reranking**:

```python
# During index creation
manager = create_rag_retriever(
    doc_dir="...",
    retriever_types=["hybrid"],
    reranker_model="bge-large"  # Enable reranker
)

# During search
results = manager.search(
    query="...",
    retriever_type="hybrid",
    top_k=10,
    use_reranker=True  # Use reranker for this query
)
```

**CLI Usage**:

```bash
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --reranker bge-large \
    --top-k 10
```

### Performance Impact

**Without Reranking**:
- Initial retrieval: ~10-50ms
- Total: ~10-50ms

**With Reranking** (top_k=10, multiplier=3):
- Initial retrieval: ~10-50ms
- Reranking 30 candidates: ~200-500ms
- Total: ~210-550ms

**Trade-offs**:
- **Quality**: Significant improvement (10-30% better nDCG)
- **Speed**: 5-10x slower
- **Use When**: Quality is more important than speed

### Best Practices

1. **Use Reranking For**:
   - Production systems requiring high quality
   - Final answer generation
   - When initial retrieval quality is insufficient

2. **Skip Reranking For**:
   - Development and testing
   - Real-time systems with strict latency requirements
   - When initial retrieval quality is sufficient

3. **Reranker Selection**:
   - **BGE-Large**: Maximum quality, production systems
   - **BGE-Base**: Balanced, good quality improvement
   - **MiniLM-L12**: Fast reranking, moderate improvement

---

## Phase 6: Answer Generation

### Overview

Answer generation uses Large Language Models (LLMs) to synthesize answers from retrieved documents. The system supports multiple LLM providers and includes proper citation formatting.

**Location**: `src/generation/generator.py`

**Default Model**: GPT-4o-mini (OpenAI)

### Supported Providers

**1. OpenAI**

- **Models**: GPT-4o-mini, GPT-4o, GPT-4-turbo, GPT-3.5-turbo
- **API**: OpenAI API
- **Configuration**: `OPENAI_API_KEY` environment variable

**2. Azure OpenAI**

- **Models**: Same as OpenAI
- **API**: Azure OpenAI Service
- **Configuration**: `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT`

**3. Ollama** (Local)

- **Models**: llama2, mistral, codellama, etc.
- **API**: Local Ollama server
- **Configuration**: `base_url="http://localhost:11434"`

### Generation Process

**Step-by-Step**:

1. **Retrieve Documents**: Get relevant chunks/pages from retrieval system
2. **Format Context**: Combine retrieved documents into prompt context
3. **Generate Answer**: Send query + context to LLM
4. **Extract Citations**: Parse citations from LLM response
5. **Format Output**: Structure answer with citations and metadata

**Key Implementation**:

```python
class RAGGenerator:
    def generate(
        self,
        query: str,
        retrieved_docs: List[Dict],
        include_citations: bool = True
    ) -> Dict:
        """
        1. Format context from retrieved documents
        2. Build prompt with citation instructions
        3. Call LLM API
        4. Parse response and extract citations
        5. Return structured answer
        """
```

### Prompt Engineering

**Citation Format**:

The system uses markdown hyperlinks for citations:

- **Text chunks**: `[1.1](#chunk-1-1)`, `[1.2](#chunk-1-2)`, etc.
- **Images**: `[2.1](#image-2-1)`, `[2.2](#image-2-2)`, etc.

**Prompt Template**:

```python
CITATION_PROMPT_TEMPLATE = """
You are a helpful AI assistant that answers questions based on the provided context documents.

IMPORTANT INSTRUCTIONS:
1. Use ONLY information from the provided context to answer the question
2. Include inline citations as MARKDOWN HYPERLINKS:
   - Text chunks: [1.1](#chunk-1-1), [1.2](#chunk-1-2), etc.
   - Images: [2.1](#image-2-1), [2.2](#image-2-2), etc.
3. If the context doesn't contain enough information, say so clearly
4. Be concise but thorough
5. OUTPUT YOUR ANSWER IN MARKDOWN FORMAT

CONTEXT DOCUMENTS:
{context}

QUESTION: {question}

Provide your answer in MARKDOWN format with inline citations.
"""
```

**Context Formatting**:

```python
def format_context(retrieved_docs):
    """
    Format retrieved documents for prompt:
    
    [1.1] Text chunk from document1.md
    Content: ...
    
    [1.2] Text chunk from document1.md
    Content: ...
    
    [2.1] Image from document2.pdf, page 5
    Description: ...
    """
```

### Citation Parsing

**Citation Extraction**:

The system parses citations from LLM responses:

```python
def extract_citations(answer_text: str) -> Dict:
    """
    Extract citations from answer:
    - Find all [X.Y](#chunk-X-Y) or [X.Y](#image-X-Y) patterns
    - Map to source documents
    - Return structured citation data
    """
```

**Citation Structure**:

```python
{
    "answer": "The main topic is machine learning [1.1](#chunk-1-1)...",
    "citations": {
        "1.1": {
            "type": "text",
            "source": "document1.md",
            "chunk_index": 0,
            "text": "Machine learning is..."
        },
        "2.1": {
            "type": "image",
            "source": "document2.pdf",
            "page": 5,
            "description": "..."
        }
    },
    "files": {
        "1": "document1.md",
        "2": "document2.pdf"
    }
}
```

### Output Format

**Structured Response**:

```python
{
    "answer": "Markdown formatted answer with citations...",
    "citations": {
        "1.1": {...},
        "1.2": {...},
        "2.1": {...}
    },
    "files": {
        "1": "document1.md",
        "2": "document2.pdf"
    },
    "contents": {
        "1.1": {
            "text": "Full chunk text...",
            "filename": "document1.md",
            "score": 0.892
        }
    },
    "metadata": {
        "model": "gpt-4o-mini",
        "provider": "openai",
        "tokens_used": 1250,
        "retrieved_docs": 10
    }
}
```

### Configuration

**GenerationConfig**:

```python
@dataclass
class GenerationConfig:
    provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.0  # Deterministic
    max_tokens: int = 2000
    enable_citations: bool = True
    citation_style: str = "numbered"
```

**Usage**:

```python
# Create generator
config = GenerationConfig(
    provider="openai",
    model_name="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY")
)
generator = RAGGenerator(config)

# Generate answer
result = generator.generate(
    query="What is machine learning?",
    retrieved_docs=retrieved_documents,
    include_citations=True
)
```

### Error Handling

**API Errors**:
- Rate limiting: Automatic retry with exponential backoff
- Invalid API key: Clear error message
- Model unavailable: Fallback to alternative model
- Timeout: Retry with increased timeout

**Context Length**:
- Automatic truncation if context exceeds model limits
- Prioritizes highest-scoring documents
- Warns if significant truncation occurs

### Integration with Pipeline

**Unified Query Method**:

```python
# In UnifiedRAGPipeline
result = pipeline.query(
    question="What is the main topic?",
    retriever_type="hybrid",
    top_k=10,
    generate=True,  # Enable generation
    use_reranker=True
)

# Result includes:
# - text_docs: Text retrieval results
# - image_docs: Image retrieval results
# - answer: Generated answer with citations
# - citations: Structured citation data
```

---

## Phase 7: Evaluation & Benchmarking

### Overview

The evaluation system provides standard retrieval metrics to measure and compare retrieval quality across different methods and configurations.

**Location**: `src/evaluation/metrics.py`, `src/evaluation/benchmark.py`

### Available Metrics

**1. Recall@K**

- **Definition**: Proportion of relevant documents retrieved in top K
- **Range**: 0.0 to 1.0 (higher is better)
- **Use Case**: Measures coverage of relevant documents

**Formula**:
```
Recall@K = |Relevant ∩ Retrieved@K| / |Relevant|
```

**2. nDCG@K (Normalized Discounted Cumulative Gain)**

- **Definition**: Normalized version of DCG, accounts for ranking position
- **Range**: 0.0 to 1.0 (higher is better)
- **Use Case**: Measures ranking quality with position weighting

**Formula**:
```
DCG@K = Σ(rel_i / log2(i+1)) for i=1 to K
nDCG@K = DCG@K / IDCG@K
```

**3. MRR (Mean Reciprocal Rank)**

- **Definition**: Average of reciprocal ranks of first relevant document
- **Range**: 0.0 to 1.0 (higher is better)
- **Use Case**: Measures how quickly first relevant document appears

**Formula**:
```
MRR = (1/N) * Σ(1 / rank_i) for i=1 to N queries
```

**4. MAP (Mean Average Precision)**

- **Definition**: Average precision across all queries
- **Range**: 0.0 to 1.0 (higher is better)
- **Use Case**: Overall retrieval quality metric

**Formula**:
```
AP = (1/|Relevant|) * Σ(Precision@i) for i where doc_i is relevant
MAP = (1/N) * Σ(AP_i) for i=1 to N queries
```

### Implementation

**Metrics Functions**:

```python
def recall_at_k(retrieved: List[Tuple[str, float]], 
                relevant: Dict[str, int], 
                k: int) -> float:
    """Calculate Recall@K"""
    
def ndcg_at_k(retrieved: List[Tuple[str, float]], 
              relevant: Dict[str, int], 
              k: int) -> float:
    """Calculate nDCG@K"""
    
def mrr(retrieved: List[Tuple[str, float]], 
        relevant: Dict[str, int]) -> float:
    """Calculate MRR"""
    
def map_score(retrieved: List[Tuple[str, float]], 
              relevant: Dict[str, int]) -> float:
    """Calculate MAP"""
```

### Benchmark Runner

**Location**: `src/evaluation/benchmark.py`

**Class**: `BenchmarkRunner`

**Purpose**: Run comprehensive benchmarks across multiple retrievers and configurations.

**Key Features**:
- Evaluate multiple retriever types
- Test with/without reranking
- Multiple K values
- Per-query and aggregate metrics
- Export results to JSON

**Usage**:

```python
from src.evaluation import BenchmarkConfig, BenchmarkRunner

config = BenchmarkConfig(
    queries_path="data/queries.jsonl",
    qrels_path="data/qrels.tsv",
    retriever_types=["bm25", "dense", "hybrid"],
    reranker_models=[None, "bge-large"],
    k_values=[1, 3, 5, 10]
)

runner = BenchmarkRunner(config)
results = runner.run(retriever_manager)
runner.print_summary()
runner.save_results("benchmark_results.json")
```

### Query File Format

**JSONL Format** (recommended):

```jsonl
{"id": "q1", "text": "What is machine learning?"}
{"id": "q2", "text": "How do neural networks work?"}
{"id": "q3", "text": "Explain backpropagation"}
```

**JSON Format**:

```json
[
    {"id": "q1", "text": "What is machine learning?"},
    {"id": "q2", "text": "How do neural networks work?"}
]
```

### Qrels File Format

**TSV Format** (TREC-style):

```
q1	0	doc1	1
q1	0	doc2	0
q1	0	doc3	1
q2	0	doc1	1
q2	0	doc2	1
```

**Format**: `query_id \t 0 \t doc_id \t relevance`

- **relevance**: 0 = not relevant, 1+ = relevant (higher = more relevant)

### Benchmark Results

**Output Structure**:

```json
{
    "config": {
        "retriever_types": ["bm25", "dense", "hybrid"],
        "reranker_models": [null, "bge-large"],
        "k_values": [1, 3, 5, 10]
    },
    "results": {
        "bm25": {
            "no_reranker": {
                "recall@1": 0.45,
                "recall@5": 0.72,
                "recall@10": 0.85,
                "ndcg@10": 0.68,
                "mrr": 0.52,
                "map": 0.61
            }
        },
        "hybrid": {
            "no_reranker": {...},
            "bge_large": {
                "recall@10": 0.91,
                "ndcg@10": 0.82,
                ...
            }
        }
    },
    "per_query": {
        "q1": {
            "bm25": {...},
            "dense": {...},
            "hybrid": {...}
        }
    }
}
```

### Quick Benchmark Function

**Convenience Function**:

```python
from src.evaluation import run_retrieval_benchmark

results = run_retrieval_benchmark(
    retriever_manager,
    queries_path="data/queries.jsonl",
    qrels_path="data/qrels.tsv",
    retriever_types=["bm25", "dense", "hybrid"],
    use_reranker=True
)
```

### Integration with Pipeline

**CLI Usage**:

```bash
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode full \
    --evaluate \
    --queries ms_marco_val/queries.jsonl
```

**Python API**:

```python
pipeline = UnifiedRAGPipeline(input_dir, output_dir, config)
pipeline.config.enable_evaluation = True

results = pipeline.run(queries=queries)
# Evaluation results saved to output/evaluation/
```

---

## Phase 8: Web Interface

### Overview

The web interface provides a modern, user-friendly way to interact with the RAG pipeline through a React frontend and FastAPI backend.

**Frontend**: `frontend/`
**Backend**: `api/main.py`

### Frontend Architecture

**Technology Stack**:
- **React**: UI framework
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Styling
- **Lucide React**: Icons

**Key Features**:
1. **File Upload**: Drag-and-drop file upload
2. **Processing Status**: Real-time processing pipeline visualization
3. **Indexed Files**: View indexed documents and statistics
4. **Search Interface**: Query the RAG system
5. **Results Display**: View retrieved documents and generated answers
6. **Image Preview**: View retrieved PDF pages as images

**Main Components**:

```jsx
// App.jsx structure
- FileUpload: Drag-and-drop upload
- ProcessedFilesTab: Stage pipeline visualization
- IndexedFilesTab: Index statistics and files
- SearchTab: Query interface
- ResultsDisplay: Retrieved documents and answers
- ImageGallery: PDF page preview
```

### Processing Pipeline Visualization

**Stage Indicators**:

The UI shows 4 processing stages with progress indicators:

1. **Normalized** (Sky Blue): Documents converted to PDF/Markdown
2. **Media Processed** (Cyan): Video/audio transcripts
3. **Chunked** (Blue): Documents split into chunks
4. **RAG Ready** (Indigo): Final RAG-ready format

**Features**:
- Filter by stage
- Document grouping by source
- Expandable file details
- Progress tracking

### Indexed Files Dashboard

**Two-Card Layout**:

1. **Text Index Card**:
   - Chunks count
   - Documents count
   - Active retrievers (BM25, Dense, Hybrid)
   - Indexed files list

2. **Image Index Card**:
   - Pages count
   - PDF files count
   - Model info (ColQwen version, quantization)
   - Indexed files list

**Statistics Display**:
- Large metric numbers with icons
- Visual indicators for index readiness
- Rebuild index button

### Search Interface

**Features**:
- Query input with auto-resize
- Retriever selection (BM25, Dense, Hybrid)
- RAG mode selection (Text, Image, Both)
- Top-K configuration
- Reranker toggle

**Results Display**:
- Retrieved documents with scores
- Generated answer with citations
- Image gallery for image results
- Expandable document previews

### Image Display

**Grid Gallery**:
- 4-column responsive grid
- Hover effects
- Score badges
- Page numbers

**Image Preview Modal**:
- Fullscreen preview
- Click to open
- Navigation between images
- Fallback icons when images unavailable

### Backend API

**Location**: `api/main.py`

**Framework**: FastAPI

**Key Endpoints**:

```python
# File Management
POST /api/upload              # Upload files
GET  /api/files               # List files
DELETE /api/files/{path}      # Delete file

# Processing
POST /api/process             # Start processing
GET  /api/status              # Get processing status

# Indexing
POST /api/index               # Build index
GET  /api/index/status        # Get index status

# Search
POST /api/search              # Search query
GET  /api/image/{path}        # Serve images

# Statistics
GET  /api/stats               # Get pipeline statistics
```

**CORS Configuration**:
- Configured for `localhost:3000` (frontend)
- Allows all origins in development

**File Serving**:
- Serves images from output directories
- Proper MIME types
- FileResponse for efficient streaming

### Real-Time Updates

**Status Polling**:
- Frontend polls `/api/status` every 5 seconds
- Updates processing progress
- Shows index readiness
- Displays statistics

**Progress Indicators**:
- Upload progress with percentage
- Processing stage indicators
- Loading spinners
- Success/error messages

### UI Design

**Color Scheme**:
- Primary: Light blue (#0ea5e9)
- Secondary: Sky blue (#06b6d4)
- Accent: Blue (#3b82f6)
- Background: Gradient with blur effects

**Modern Features**:
- Glassmorphism effects
- Smooth animations
- Hover interactions
- Responsive design
- Dark mode ready (future)

### Running the Web Interface

**Backend**:

```bash
cd api
pip install -r requirements.txt
python main.py
# Server runs on http://localhost:8000
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

**Access**:
- Open browser to `http://localhost:3000`
- Upload documents
- Process and index
- Search and query

---

## Architecture & Integration

### System Architecture

**High-Level Flow**:

```
Input Documents
    ↓
[Phase 1] Document Processing Pipeline
    ├── Normalization
    ├── Media Processing
    ├── Document Processing (Docling)
    └── Consolidation
    ↓
RAG-Ready Documents (stage4_rag_ready/)
    ↓
[Phase 2] Text Chunking
    ↓
Chunked Documents
    ↓
[Phase 3] Text-Based Retrieval Indexing
    ├── BM25 Index
    ├── Dense Index (FAISS)
    └── Hybrid Index
    ↓
[Phase 4] Image-Based Retrieval Indexing
    └── ColQwen Index
    ↓
Ready for Querying
    ↓
[Phase 5] Reranking (Optional)
    ↓
[Phase 6] Answer Generation
    ↓
Final Answer with Citations
```

### Component Integration

**UnifiedRAGPipeline**:

The main orchestrator that coordinates all phases:

```python
class UnifiedRAGPipeline:
    def __init__(self, input_dir, output_dir, config):
        # Initialize components
        self.document_processor = None
        self.retriever_manager = None
        self.image_retriever_manager = None
        self.generator = None
    
    def run(self):
        # Phase 1: Document Processing
        if config.enable_processing:
            self.run_document_processing()
        
        # Phase 2-3: Setup Text Retrievers
        if config.enable_retrieval:
            self.setup_retrievers()
        
        # Phase 4: Setup Image Retrievers
        if config.enable_image_retrieval:
            self.setup_image_retrievers()
        
        # Phase 7: Evaluation (if queries provided)
        if queries:
            self.run_retrieval_evaluation(queries)
    
    def query(self, question, ...):
        # Phase 3-4: Retrieve documents
        text_docs = self.retriever_manager.search(...)
        image_docs = self.image_retriever_manager.search(...)
        
        # Phase 5: Rerank (optional)
        if use_reranker:
            text_docs = self._rerank(...)
        
        # Phase 6: Generate answer
        answer = self.generator.generate(...)
        
        return result
```

### Data Flow

**Document Processing Flow**:

```
input/
├── document1.docx
├── document2.pdf
└── video1.mp4
    ↓
stage1_normalized/
├── normalized_pdfs/
│   ├── document1.pdf
│   └── document2.pdf (copied)
├── normalized_markdown/
└── original_files/
    └── document1.docx
    ↓
stage2_media_processed/
└── transcripts/
    └── video1.md
    ↓
stage3_document_processed/
├── document1/
│   └── document1.md
├── document2/
│   └── document2.md
└── video1/
    └── video1.md
    ↓
stage4_rag_ready/
├── document1/
│   ├── document1.pdf
│   ├── document1.md
│   └── docling_additional/
├── document2/
│   ├── document2.pdf
│   └── document2.md
└── video1/
    └── video1.md
```

**Retrieval Index Flow**:

```
stage4_rag_ready/
    ↓
Text Chunking
    ↓
Chunked Documents
    ↓
┌─────────────────┬──────────────────┐
│                 │                  │
BM25 Index    Dense Index      Hybrid Index
│                 │                  │
└─────────────────┴──────────────────┘
    ↓
output/retrieval/
├── documents.json
├── index_meta.json
├── bm25/
├── dense/
└── hybrid/
```

**Image Retrieval Flow**:

```
stage4_rag_ready/ (PDFs)
    ↓
PDF to Image Conversion
    ↓
Page Images
    ↓
ColQwen Embeddings
    ↓
output/image_retrieval/
└── colqwen/
    ├── colqwen_index.pkl
    └── colqwen_meta.json
```

### Output Directory Structure

```
output/
├── processing/
│   ├── stage1_normalized/
│   ├── stage2_media_processed/
│   ├── stage3_document_processed/
│   └── stage4_rag_ready/          # 🎯 RAG-ready documents
│
├── retrieval/                      # Text retrieval indexes
│   ├── documents.json
│   ├── index_meta.json
│   ├── bm25/
│   ├── dense/
│   └── hybrid/
│
├── image_retrieval/               # Image retrieval indexes
│   ├── image_index_meta.json
│   └── colqwen/
│
├── logs/                          # Pipeline logs
│   ├── rag_pipeline_*.log
│   ├── retrieval_*.log
│   └── generation_*.log
│
├── evaluation/                    # Evaluation results
│   └── retrieval_evaluation_results.json
│
└── unified_rag_pipeline_stats.json
```

### Module Dependencies

**Processing Modules**:
- `processor/normalizer.py` → LibreOffice, Poppler
- `processor/media_processor.py` → FFmpeg, Whisper
- `processor/document_processor.py` → Docling, OCR engines
- `processor/consolidator.py` → File operations

**Retrieval Modules**:
- `retrieval/rag_retrievers.py` → BM25, SentenceTransformers, FAISS
- `retrieval/image_retrievers.py` → ColQwen, pdf2image
- `chunking/chunker.py` → LangChain (optional)

**Generation Modules**:
- `generation/generator.py` → OpenAI, Azure OpenAI, Ollama

**Evaluation Modules**:
- `evaluation/metrics.py` → NumPy
- `evaluation/benchmark.py` → Uses metrics.py

---

## Configuration System

### Configuration Hierarchy

**Priority Order** (highest to lowest):
1. CLI arguments
2. YAML configuration file
3. Default values

### YAML Configuration

**Location**: `config/default.yaml`

**Structure**:

```yaml
pipeline:
  mode: "full"
  rag_mode: "both"
  enable_processing: true
  enable_retrieval: true

processing:
  enable_normalization: true
  enable_media_processing: true
  enable_document_processing: true
  use_gpu: true

text_retrieval:
  methods: ["bm25", "dense", "hybrid"]
  default_method: "hybrid"
  top_k: 10
  chunking:
    enabled: true
    chunk_size: 1000
    chunk_overlap: 200
  reranker:
    enabled: false
    model: null

image_retrieval:
  enabled: true
  methods: ["colqwen"]
  top_k: 5
  colqwen:
    model: "vidore/colqwen2-v1.0"
    dtype: "bfloat16"
    quantization: "8bit"
    pdf_dpi: 150

generation:
  enabled: true
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.0
  max_tokens: 2000
```

### CLI Configuration

**Usage**:

```bash
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --config config/default.yaml \
    --mode full \
    --rag-mode both \
    --reranker bge-large \
    --top-k 10 \
    --chunk-size 1000
```

**Key Arguments**:
- `--input`, `-i`: Input directory
- `--output`, `-o`: Output directory
- `--config`, `-c`: YAML config file
- `--mode`: processing, retrieval, full, test
- `--rag-mode`: text, image, both
- `--retrievers`: bm25, dense, hybrid
- `--reranker`: bge-large, minilm-l12, bge-base, none
- `--top-k`: Number of results
- `--chunk-size`: Chunk size in characters
- `--chunk-overlap`: Overlap between chunks

### Python API Configuration

**UnifiedRAGConfig**:

```python
from src import UnifiedRAGPipeline, UnifiedRAGConfig
from src.processor.pipeline import PipelineConfig
from src.generation.generator import GenerationConfig

# Create configuration
config = UnifiedRAGConfig(
    enable_processing=True,
    enable_retrieval=True,
    rag_mode="both",
    retrieval_methods=["bm25", "dense", "hybrid"],
    retrieval_top_k=10,
    enable_reranker=True,
    reranker_model="bge-large",
    chunk_size=1000,
    chunk_overlap=200,
    enable_image_retrieval=True,
    image_retrieval_top_k=5,
    enable_generation=True,
    generation_config=GenerationConfig(
        provider="openai",
        model_name="gpt-4o-mini"
    )
)

# Initialize pipeline
pipeline = UnifiedRAGPipeline("input/", "output/", config)
```

### Environment Variables

**API Keys**:
- `OPENAI_API_KEY`: OpenAI API key
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint

**System Paths**:
- Ensure LibreOffice, FFmpeg, Tesseract are in PATH
- Or configure paths in code

---

## Performance Optimization

### Processing Optimization

**Fast Mode**:
- Disables VLM processing (3-5x faster)
- Disables image/table extraction
- Still extracts all text content
- Use for development/testing

```bash
python run_pipeline.py --input input/ --output output/ --fast-mode
```

**GPU Acceleration**:
- CUDA required for Docling VLM models
- Significant speedup for large documents
- Automatic fallback to CPU if GPU unavailable

**Parallel Processing**:
- Future enhancement: Process multiple files in parallel
- Currently sequential for stability

### Retrieval Optimization

**Index Persistence**:
- Save indexes to disk after building
- Load existing indexes for fast startup
- Avoids re-indexing on every run

**FAISS GPU**:
- Use GPU FAISS for faster vector search
- Install: `pip install faiss-gpu`
- Automatic fallback to CPU FAISS

**Chunking Strategy**:
- Smaller chunks = more precise retrieval
- Larger chunks = more context
- Balance based on use case

### Memory Optimization

**ColQwen Quantization**:
- 4-bit: ~2.5GB VRAM (from ~7GB)
- 8-bit: ~4GB VRAM
- Trade-off: Slightly reduced quality

**Batch Processing**:
- Process documents in batches
- Clear GPU memory between batches
- Prevents OOM errors

**Model Loading**:
- Lazy loading: Load models only when needed
- Unload models after use
- Share models across components

### Caching

**Processing Cache**:
- Skip already-processed files
- Hash-based change detection
- Cache file: `.processing_cache.json`

**Index Cache**:
- Save indexes to disk
- Load on startup if available
- Rebuild only if documents change

### Best Practices

1. **Development**:
   - Use `--fast-mode` for quick iteration
   - Disable image retrieval
   - Use smaller chunk sizes

2. **Production**:
   - Enable all features
   - Use GPU acceleration
   - Enable reranking for quality
   - Use appropriate chunk sizes

3. **Large Corpora**:
   - Process in batches
   - Use index persistence
   - Consider approximate nearest neighbor search
   - Monitor memory usage

---

## Conclusion

This Unified RAG Pipeline provides a complete, production-ready solution for document processing and information retrieval. It combines:

- **Robust Document Processing**: Handles any format, extracts structured content
- **Multiple Retrieval Strategies**: BM25, Dense, Hybrid for different use cases
- **Image-Based Retrieval**: ColQwen for visual document understanding
- **Quality Improvements**: Reranking for better results
- **Answer Generation**: LLM integration with proper citations
- **Evaluation Tools**: Standard metrics for quality measurement
- **Modern Interface**: Web UI for easy interaction

The system is modular, extensible, and designed for both development and production use. Each phase can be used independently or combined for complete RAG workflows.

---

## Appendix

### File Locations Reference

**Core Pipeline**:
- `run_pipeline.py`: Main entry point
- `src/unified_rag_pipeline.py`: Pipeline orchestrator

**Processing**:
- `src/processor/pipeline.py`: Processing orchestrator
- `src/processor/normalizer.py`: Stage 1
- `src/processor/media_processor.py`: Stage 2
- `src/processor/document_processor.py`: Stage 3
- `src/processor/consolidator.py`: Stage 4

**Retrieval**:
- `src/retrieval/rag_retrievers.py`: Text retrieval
- `src/retrieval/image_retrievers.py`: Image retrieval
- `src/chunking/chunker.py`: Text chunking

**Generation**:
- `src/generation/generator.py`: Answer generation

**Evaluation**:
- `src/evaluation/metrics.py`: Metrics implementation
- `src/evaluation/benchmark.py`: Benchmark runner

**Web Interface**:
- `api/main.py`: FastAPI backend
- `frontend/src/App.jsx`: React frontend

**Configuration**:
- `config/default.yaml`: Default configuration

### Quick Reference Commands

**Complete Pipeline**:
```bash
python run_pipeline.py --input input/ --output output/ --mode full
```

**Processing Only**:
```bash
python run_pipeline.py --input input/ --output output/ --mode processing
```

**Retrieval Only**:
```bash
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode retrieval
```

**Test Mode**:
```bash
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode test --interactive
```

**With Reranking**:
```bash
python run_pipeline.py --input input/ --output output/ --reranker bge-large --top-k 10
```

**Image RAG**:
```bash
python run_pipeline.py --input input/ --output output/ --rag-mode image --image-retrieval
```

**Both Text + Image**:
```bash
python run_pipeline.py --input input/ --output output/ --rag-mode both --image-retrieval --top-k 10 --image-top-k 5
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-01  
**Authors**: QPhu (Document Processing), NKhoi (Information Retrieval)



