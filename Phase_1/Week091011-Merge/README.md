# Unified RAG Pipeline

A comprehensive, production-ready pipeline that combines **document processing** and **information retrieval** into a complete RAG (Retrieval-Augmented Generation) system.

**Combines the best of both worlds:**
- 📄 **Document Processing Pipeline** (Week070809_QPhu_Processor) - Ingestion, normalization, and processing
- 🔍 **Information Retrieval Pipeline** (Week070809_NKhoi_Retrieval) - Multiple retrieval strategies and evaluation

**Platform Support:** Windows | macOS | Linux  
**Python Version:** 3.9+

## 🎯 Overview

This unified pipeline handles the complete RAG workflow from raw documents to retrieval-ready systems:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INPUT: Any Document Type                          │
│   DOCX, PPTX, PDF, HTML, Images, Excel, CSV, Video, Audio, etc.    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 DOCUMENT PROCESSING PIPELINE                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Stage 1   │  │   Stage 2   │  │   Stage 3   │  │   Stage 4   │ │
│  │Normalization│  │   Media     │  │  Docling    │  │Consolidation│ │
│  │             │  │ Processing  │  │ Processing  │  │             │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RAG-READY DOCUMENTS                             │
│              📄 file.md + 🖼️ file.pdf + 📊 extras                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TEXT CHUNKING                                  │
│     Recursive Character Text Splitting (1000 chars, 200 overlap)   │
│              📄 Document → 📝 Chunk 1, Chunk 2, ... Chunk N         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                INFORMATION RETRIEVAL PIPELINE                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │    BM25     │  │   Dense     │  │   Hybrid    │  │  Reranker   │ │
│  │  (Sparse)   │  │ (Semantic)  │  │ (RRF 130%)  │  │ (Optional)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              IMAGE-BASED RETRIEVAL (Optional)                   ││
│  │                    ColQwen 2.5 Vision-Language                  ││
│  └─────────────────────────────────────────────────────────────────┘│
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANSWER GENERATION (LLM)                          │
│    Query + Retrieved Chunks/Images → GPT-4o-mini → Answer + Citations│
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start (3 Minutes)

```bash
# 1. Clone and setup
git clone <your-repo-url>
cd Week091011-Merge

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install system dependencies (see Installation section)

# 5. Run the complete pipeline
python run_pipeline.py --input input/ --output output/ --mode full

# 6. Or run individual components
python run_pipeline.py --input input/ --output output/ --mode processing
python run_pipeline.py --input input/ --output output/ --mode retrieval
```

**That's it!** Your documents are processed and retrieval systems are ready.

## 📁 Project Structure

```
Week091011-Merge/
├── README.md                    # This comprehensive guide
├── USAGE.md                     # Detailed CLI usage guide
├── requirements.txt             # Unified dependencies
├── run_pipeline.py              # 🎯 MAIN ENTRY POINT
│
├── src/                         # Source code
│   ├── unified_rag_pipeline.py  # Pipeline orchestrator
│   ├── processor/               # Document processing components
│   │   ├── pipeline.py          # Processing orchestrator
│   │   ├── normalizer.py        # Stage 1: Normalization
│   │   ├── media_processor.py   # Stage 2: Media processing
│   │   ├── document_processor.py # Stage 3: Docling processing
│   │   ├── consolidator.py      # Stage 4: RAG-ready consolidation
│   │   └── utils.py             # Utilities
│   ├── chunking/                # Text chunking components
│   │   └── chunker.py           # Recursive text splitter
│   ├── retrieval/               # Information retrieval components
│   │   ├── rag_retrievers.py    # BM25, Dense, Hybrid + Reranker
│   │   ├── image_retrievers.py  # ColQwen image-based retrieval
│   │   └── chunking_utils.py    # Chunking utilities for retrieval
│   ├── evaluation/              # Benchmark & metrics
│   │   ├── metrics.py           # nDCG, Recall, MRR, MAP
│   │   └── benchmark.py         # BenchmarkRunner for evaluation
│   └── generation/              # Answer generation components
│       └── generator.py         # LLM-based answer generation
│
├── input/                       # 📥 Place your documents here
├── output/                      # 📤 Processing outputs (auto-created)
│   ├── processing/              # Document processing results
│   │   └── stage4_rag_ready/    # 🎯 Final RAG-ready documents
│   ├── retrieval/               # Retrieval indexes (chunked)
│   ├── image_retrieval/         # Image retrieval indexes (ColQwen)
│   ├── logs/                    # Pipeline logs
│   └── evaluation/              # Evaluation results
│
└── docs/                        # Documentation
    └── MODAL_USAGE.md           # Modal deployment guide
```

## ⚡ Usage Examples

### 1. Complete RAG Pipeline (Recommended)

```bash
# Process documents + setup retrieval systems
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode full \
    --retrievers bm25 dense hybrid
```

### 2. Text-based RAG with Reranking

```bash
# Use hybrid retrieval with BGE-Large reranker
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode text \
    --reranker bge-large \
    --top-k 10
```

### 3. Image-based RAG (ColQwen)

```bash
# Use ColQwen for visual document retrieval
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode image \
    --image-top-k 5
```

### 4. Combined Text + Image RAG

```bash
# Use both text and image retrieval
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode both \
    --top-k 10 \
    --image-top-k 3
```

### 5. Document Processing Only

```bash
# Just process documents to RAG-ready format
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode processing \
    --fast-mode
```

### 6. Retrieval Setup Only

```bash
# Setup retrieval on existing processed documents
python run_pipeline.py \
    --input output/processing/stage4_rag_ready/ \
    --output output/ \
    --mode retrieval \
    --retrievers bm25 dense hybrid
```

### 7. Test Mode (Demo/Testing)

```bash
# Test with already processed documents
python run_pipeline.py \
    --input output/processing/stage4_rag_ready/ \
    --output output/ \
    --mode test

# Interactive testing
python run_pipeline.py \
    --input output/processing/stage4_rag_ready/ \
    --output output/ \
    --mode test \
    --interactive
```

### 8. With Evaluation Benchmark

```bash
# Run benchmark evaluation
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode full \
    --evaluate \
    --queries evaluation_queries.json
```

## 🔧 Configuration Options

### Pipeline Modes

| Mode | Description | Components |
|------|-------------|------------|
| `processing` | Document processing only | Normalization → Media → Docling → Consolidation |
| `retrieval` | Retrieval setup only | BM25, Dense, Hybrid |
| `full` | Complete pipeline | Processing + Retrieval + Evaluation |
| `test` | Test/demo mode | Interactive querying of processed documents |

### RAG Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `text` | Text-based retrieval only | General Q&A, text-heavy documents |
| `image` | Image-based retrieval only | Visual documents, diagrams, charts |
| `both` | Combined text + image | Best coverage, multi-modal RAG |

### Reranker Options

| Model | Description | Performance |
|-------|-------------|-------------|
| `none` | No reranking (default) | Fastest |
| `bge-large` | BGE-Large Reranker | Best quality |
| `minilm-l12` | MiniLM Cross-Encoder | Balanced |
| `bge-base` | BGE-Base Reranker | Faster than large |

### Processing Options

| Flag | Description | Default |
|------|-------------|---------|
| `--skip-normalization` | Skip document normalization | False |
| `--skip-media` | Skip video/audio processing | False |
| `--fast-mode` | Disable VLM for faster processing | False |
| `--no-gpu` | Force CPU-only processing | False |

### Chunking Options

| Flag | Description | Default |
|------|-------------|---------|
| `--chunk-size` | Chunk size in characters | 1000 |
| `--chunk-overlap` | Overlap between chunks | 200 |
| `--no-chunking` | Disable chunking (use full docs) | False |

### Retrieval Options

| Flag | Description | Default |
|------|-------------|---------|
| `--retrievers` | Retrieval methods to use | `bm25`, `dense`, `hybrid` |
| `--top-k` | Number of text chunks to retrieve | 10 |
| `--image-top-k` | Number of image pages to retrieve | 5 |
| `--rag-mode` | RAG mode (`text`, `image`, `both`) | `text` |
| `--reranker` | Reranker model | `none` |
| `--evaluate` | Enable retrieval evaluation | Flag |
| `--queries` | Path to evaluation queries | JSON/JSONL file |

### Generation Options

| Flag | Description | Default |
|------|-------------|---------|
| `--no-generation` | Disable answer generation | False |
| `--llm-provider` | LLM provider | `openai` |
| `--llm-model` | LLM model name | `gpt-4o-mini` |
| `--api-key` | API key for LLM | env var |

### Logging Options

| Flag | Description | Default |
|------|-------------|---------|
| `--log-level` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `--no-log-file` | Disable logging to file | False |

## 📊 Document Processing Pipeline

### Stage 1: Normalization
- **DOCX/PPTX/HTML** → PDF (for image-based RAG)
- **Images** → PDF (for image-based RAG)
- **TXT** → Markdown (simple text files)
- **Copy ALL originals** to `original_files/` (for Docling)

### Stage 2: Media Processing
- **Video** → Audio → Text transcription (Whisper)
- **Audio** → Text transcription (Whisper)
- **Export formats**: .json, .srt, .vtt, .txt, .md
- **Optional**: Extract video frames for image retrieval

### Stage 3: Document Processing (Docling)
- **Smart deduplication**: Process each file only once
- **Priority processing**: Normalized PDFs → Originals → Markdown → Transcripts
- **Deep analysis**: OCR, VLM, table extraction, image extraction
- **GPU acceleration**: CUDA support for faster processing

### Stage 4: Consolidation
- **Unified structure**: `file.pdf` + `file.md` + `docling_additional/`
- **RAG-ready output**: Consistent format for all document types
- **Easy integration**: Single directory for RAG systems

## 📝 Text Chunking

Documents are split into smaller chunks for better retrieval precision:

### Chunking Strategy

Uses **Recursive Character Text Splitting**:
1. Split by paragraphs (`\n\n`)
2. Then by lines (`\n`)
3. Then by sentences (`. `)
4. Then by words (` `)
5. Finally by characters

### Recommended Settings

| Use Case | Chunk Size | Overlap | Command |
|----------|------------|---------|---------|
| Precise Q&A | 500 | 100 | `--chunk-size 500 --chunk-overlap 100` |
| **General RAG** | **1000** | **200** | **(default)** |
| Long context | 2000 | 400 | `--chunk-size 2000 --chunk-overlap 400` |
| Full documents | N/A | N/A | `--no-chunking` |

## 🔍 Information Retrieval Pipeline

### Two Retrieval Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Text RAG** | Retrieves text chunks using BM25/Dense/Hybrid | General Q&A, text-heavy documents |
| **Image RAG** | Retrieves PDF pages using ColQwen vision model | Visual documents, diagrams, charts |

### Text Retrieval Methods

| Method | Type | Description | Use Case |
|--------|------|-------------|----------|
| **BM25** | Sparse | Keyword-based (TF-IDF) | Exact term matching |
| **Dense** | Dense | Semantic (MiniLM-L6-v2) | Semantic similarity |
| **Hybrid** | Combined | BM25 + Dense (RRF 130%) | Best of both worlds |

### Reranking (Optional)

| Reranker | Model | Description |
|----------|-------|-------------|
| **BGE-Large** | `BAAI/bge-reranker-large` | Best quality, slower |
| **MiniLM-L12** | `cross-encoder/ms-marco-MiniLM-L-12-v2` | Balanced |
| **BGE-Base** | `BAAI/bge-reranker-base` | Faster |

**How reranking works:**
1. Initial retrieval fetches `top_k * 3` candidates
2. Reranker scores all candidates with cross-encoder
3. Return top `top_k` after reranking

### Image Retrieval Methods

| Method | Model | Description | Use Case |
|--------|-------|-------------|----------|
| **ColQwen** | `vidore/colqwen2.5-v0.2` | Vision-language embeddings | Diagrams, charts, visual layouts |

ColQwen uses a vision-language model to understand and retrieve based on visual content, not just text.

### Hybrid Expansion

When using `--retrievers hybrid`:
- Retrieves **130%** of requested `top-k` from each retriever
- Example: `--top-k 10` → BM25 gets 13, Dense gets 13
- Results fused using **Reciprocal Rank Fusion (RRF)**
- Final output: exactly `top-k` results with best combined ranking

## 📈 Evaluation & Benchmarking

### Built-in Metrics

| Metric | Description |
|--------|-------------|
| **Recall@K** | Proportion of relevant documents in top-K |
| **nDCG@K** | Normalized Discounted Cumulative Gain |
| **MRR** | Mean Reciprocal Rank |
| **MAP** | Mean Average Precision |

### Running Benchmarks

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
runner.save_results()
```

### Quick Benchmark

```python
from src.evaluation import run_retrieval_benchmark

run_retrieval_benchmark(
    retriever_manager,
    queries_path="data/queries.jsonl",
    qrels_path="data/qrels.tsv",
    retriever_types=["bm25", "dense", "hybrid"],
    use_reranker=True
)
```

## 🛠️ Installation

### 1. Python Environment

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Install Python dependencies
pip install -r requirements.txt
```

### 2. System Dependencies

**Windows:**
- **LibreOffice**: https://www.libreoffice.org/download/
- **FFmpeg**: https://ffmpeg.org/download.html
- **Tesseract OCR**: https://github.com/UB-Mannheim/tesseract/wiki
- **Poppler**: http://blog.alivate.com.au/poppler-windows/

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y libreoffice ffmpeg tesseract-ocr poppler-utils
```

**macOS:**
```bash
brew install libreoffice ffmpeg tesseract poppler
```

### 3. GPU Support (Optional)

```bash
# For CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For GPU FAISS (faster vector search)
pip uninstall faiss-cpu
pip install faiss-gpu
```

## 📈 Performance Optimization

### Fast Mode (Development)
```bash
# 3-5x faster processing
python run_pipeline.py --input input/ --output output/ --fast-mode
```
- ✅ All text content extracted
- ✅ Tables inline in markdown  
- ❌ No VLM image descriptions
- ❌ No separate image/table files

### Balanced Mode (Production)
```bash
# Default: VLM enabled, full extraction
python run_pipeline.py --input input/ --output output/
```
- ✅ VLM image descriptions (SmolVLM-256M)
- ✅ All text + structure extracted
- ✅ Images and tables exported separately
- ⏱️ Slower but highest quality

### GPU Acceleration
- **Document Processing**: CUDA for Docling VLM models
- **Retrieval**: GPU FAISS for vector similarity search
- **ColQwen**: GPU required for image embeddings
- **Reranker**: GPU recommended for cross-encoder

## 🎓 Python API Usage

### Complete Pipeline
```python
from src import UnifiedRAGPipeline, UnifiedRAGConfig

# Configure pipeline
config = UnifiedRAGConfig(
    enable_processing=True,
    enable_retrieval=True,
    rag_mode="text",
    retrieval_methods=['bm25', 'dense', 'hybrid'],
    enable_reranker=True,
    reranker_model="bge-large"
)

# Run pipeline
pipeline = UnifiedRAGPipeline("input/", "output/", config)
results = pipeline.run()

print(f"Documents processed: {results['processing']['total_files']}")
print(f"Retrievers ready: {results['retrieval_setup']['retrievers_initialized']}")
```

### Query with Combined RAG
```python
# Query using both text and image retrieval
result = pipeline.query(
    "What does the architecture diagram show?",
    rag_mode="both",
    top_k=10,
    use_reranker=True
)

print(f"Text results: {len(result['text_docs'])}")
print(f"Image results: {len(result['image_docs'])}")
print(f"Answer: {result['answer']}")
```

### Processing Only
```python
from src.processor import DocumentProcessingPipeline, PipelineConfig

config = PipelineConfig(
    enable_normalization=True,
    enable_media_processing=True,
    enable_document_processing=True,
    use_gpu=True
)

processor = DocumentProcessingPipeline("input/", "output/", config)
stats = processor.run()
```

### Retrieval Only
```python
from src.retrieval import create_rag_retriever, load_rag_retriever

# Create retriever with chunking and reranking
manager = create_rag_retriever(
    doc_dir="output/processing/stage4_rag_ready/",
    retriever_types=["bm25", "dense", "hybrid"],
    chunk_size=1000,
    chunk_overlap=200,
    reranker_model="bge-large"
)

# Search with reranking
results = manager.search(
    "your query", 
    retriever_type="hybrid", 
    top_k=10,
    use_reranker=True
)

# Load existing index (fast)
manager = load_rag_retriever("output/retrieval/")
results = manager.search("your query", retriever_type="hybrid", top_k=10)
```

### Full RAG with Generation
```python
from src import UnifiedRAGPipeline, UnifiedRAGConfig
from src.generation import GenerationConfig

# Configure with generation
gen_config = GenerationConfig(
    provider="openai",
    model_name="gpt-4o-mini"
)

config = UnifiedRAGConfig(
    enable_processing=False,  # Use existing processed docs
    enable_retrieval=True,
    enable_generation=True,
    rag_mode="both",
    chunk_size=1000,
    retrieval_top_k=10,
    generation_config=gen_config
)

pipeline = UnifiedRAGPipeline("output/processing/stage4_rag_ready/", "output/", config)
result = pipeline.query("What is VideoRAG?", retriever_type="hybrid", top_k=10)

print(result["answer"])
print(result["citations"])
```

## 📊 Output Structure

After running the complete pipeline:

```
output/
├── processing/                  # Document processing outputs
│   ├── stage1_normalized/       # PDFs for image RAG
│   ├── stage2_media_processed/  # Audio transcripts
│   ├── stage3_document_processed/ # Docling outputs
│   └── stage4_rag_ready/        # 🎯 FINAL RAG-READY DOCUMENTS
│       ├── document1/
│       │   ├── document1.pdf    # For image-based RAG
│       │   ├── document1.md     # For text-based RAG
│       │   └── docling_additional/
│       └── document2/
│           └── document2.md
│
├── retrieval/                   # Text retrieval system outputs
│   ├── documents.json          # Chunked documents
│   ├── index_meta.json         # Index metadata (chunk config)
│   ├── bm25/                   # BM25 index
│   │   └── bm25_index.pkl
│   ├── dense/                  # Dense embeddings + FAISS
│   │   ├── faiss_index.bin
│   │   └── dense_meta.pkl
│   └── hybrid/                 # Hybrid index components
│       ├── bm25_index.pkl
│       ├── faiss_index.bin
│       └── dense_meta.pkl
│
├── image_retrieval/            # Image retrieval outputs (ColQwen)
│   ├── image_index_meta.json
│   └── colqwen/
│       ├── colqwen_index.pkl
│       └── colqwen_meta.json
│
├── logs/                        # Pipeline logs
│   ├── rag_pipeline_*.log       # Main pipeline log
│   ├── retrieval_*.log          # Retrieval operations log
│   └── generation_*.log         # Generation operations log
│
├── evaluation/                  # Evaluation results
│   └── retrieval_evaluation_results.json
│
└── unified_rag_pipeline_stats.json  # Overall statistics
```

### For RAG Integration

**Use this directory:** `output/processing/stage4_rag_ready/`

Each document folder contains:
- **file.pdf** (optional): For image-based RAG (ColPali, ColQwen)
- **file.md** (required): For text-based RAG (BM25, Dense, Hybrid)
- **docling_additional/** (optional): Images, tables, metadata

## 🔄 Integration Examples

### 1. LangChain Integration
```python
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import MarkdownTextSplitter

# Load processed documents
loader = DirectoryLoader("output/processing/stage4_rag_ready/", 
                        glob="**/*.md", 
                        loader_cls=TextLoader)
documents = loader.load()

# Split for RAG
splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(documents)
```

### 2. Custom RAG System
```python
# Use processed documents with our retrieval system
from src.retrieval import create_rag_retriever

manager = create_rag_retriever(
    doc_dir="output/processing/stage4_rag_ready/",
    retriever_types=["hybrid"],
    reranker_model="bge-large"
)

# Query with reranking
results = manager.search("What is machine learning?", top_k=5, use_reranker=True)
```

## 🚀 Deployment

### Local Development
```bash
# Quick start for development
python run_pipeline.py --input input/ --output output/ --fast-mode
```

### Production Deployment
```bash
# Full pipeline with all features
python run_pipeline.py --input input/ --output output/ --mode full --reranker bge-large
```

### Modal Deployment
See `docs/MODAL_USAGE.md` for cloud deployment instructions.

## 🤝 Contributing

This pipeline combines work from:
- **QPhu**: Document processing pipeline (Week070809_QPhu_Processor)
- **NKhoi**: Information retrieval pipeline (Week070809_NKhoi_Retrieval)

### Architecture
- **Modular design**: Each component can be used independently
- **Unified interface**: Single entry point for complete pipeline
- **Extensible**: Easy to add new retrieval methods or processing stages

## 📝 License

See LICENSE file for details.

## 🎉 Summary

This unified RAG pipeline provides:

✅ **Complete document processing** - Any format → RAG-ready  
✅ **Smart text chunking** - Recursive splitting with configurable size/overlap  
✅ **Multiple retrieval strategies** - BM25, Dense, Hybrid (130% expansion)  
✅ **Cross-encoder reranking** - BGE-Large, MiniLM for improved quality  
✅ **Image-based retrieval** - ColQwen 2.5 for visual document understanding  
✅ **Combined RAG mode** - Text + Image retrieval together  
✅ **Answer generation** - GPT-4o-mini with citations  
✅ **Evaluation & benchmarking** - nDCG, Recall, MRR, MAP metrics  
✅ **Production-ready** - GPU acceleration, error handling, logging  
✅ **Easy integration** - Simple API, consistent output format  
✅ **Index persistence** - Save/load indexes for fast startup  
✅ **Cross-platform** - Windows, macOS, Linux support  

**Ready to power your RAG applications!** 🚀
