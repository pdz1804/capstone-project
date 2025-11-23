# Capstone Project - HCMUT CS251

> **Educational Content Processing & Retrieval-Augmented Generation System**
> A comprehensive research platform for multimodal lecture processing, intelligent retrieval, and RAG pipeline development.

---

## 🎯 Project Overview

This capstone project develops an end-to-end system for processing, indexing, and querying educational content from university lectures. The system combines state-of-the-art techniques in speech recognition, optical character recognition, information retrieval, and language models to enable intelligent question-answering over lecture materials.

The project is organized into weekly development sprints, each focusing on specific components of the pipeline:

- **Document Acquisition**: Automated research paper downloading with intelligent metadata extraction
- **Multimodal Processing**: Speech-to-text transcription and slide text extraction from lectures
- **Information Retrieval**: Comparative evaluation of sparse, dense, and hybrid retrieval methods
- **RAG Systems**: Implementation and benchmarking of multiple RAG frameworks
- **Advanced Processing**: Docling-based multimodal document understanding for complex layouts

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Input Sources                             │
│  • Lecture Videos  • Slides/PDFs  • Research Papers         │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐           ┌─────▼──────┐
    │   ASR   │           │    OCR     │
    │ (Audio) │           │  (Visual)  │
    └────┬────┘           └─────┬──────┘
         │                      │
         └──────────┬───────────┘
                    │
            ┌───────▼────────┐
            │   Text Corpus  │
            └───────┬────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    ┌────▼─────┐        ┌─────▼──────┐
    │ Retrieval│        │  Indexing  │
    │ Systems  │        │  Pipeline  │
    └────┬─────┘        └─────┬──────┘
         │                    │
         └──────────┬─────────┘
                    │
            ┌───────▼────────┐
            │   RAG System   │
            │  (LLM + RAG)   │
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │   Q&A Output   │
            └────────────────┘
```

---

## 📦 Project Components

### 🔧 **Utility: Research Paper Downloader** (`downloads/`)

A robust batch downloader for academic PDFs from major venues (arXiv, ACL, CVPR, AAAI, ACM). Features intelligent metadata extraction, automatic retries, and comprehensive logging.

**Key Features**:

- Multi-venue support with site-specific heuristics
- Semantic filename generation from paper metadata
- PDF validation and deduplication
- Exponential backoff retry mechanism

---

### 📅 **Week 03-04: Foundation Development**

#### **MKhoi: ASR & OCR Pipeline** (`Week0304_MKhoi_OCR_ASR/`)

Baseline implementation for extracting text from lecture videos and slides.

**Technologies**:

- **ASR**: PhoWhisper (OpenAI Whisper variant optimized for Vietnamese)
- **OCR**: Tesseract with adaptive preprocessing
- **Audio Processing**: FFmpeg extraction, 16kHz WAV conversion
- **Batch Processing**: Multi-file support with structured outputs

**Output**: Timestamped transcripts (TXT/JSON) + extracted slide text

---

#### **NKhoi: Retrieval Systems Evaluation** (`Week0304_NKhoi_Retrieval/`)

Comprehensive comparison of retrieval methods on MS MARCO dataset.

**Methods Evaluated**:

- **BM25**: Sparse keyword-based retrieval (baseline)
- **Dense**: Sentence-BERT embeddings with cosine similarity
- **Hybrid**: Weighted Sum + Reciprocal Rank Fusion (RRF)

**Key Findings**:

- Dense retrieval achieves 3.6× higher nDCG@10 than BM25 on MS MARCO
- Hybrid methods provide marginal improvements but add complexity
- Vocabulary mismatch severely impacts BM25 on natural language queries

**Metrics**: nDCG@10, Recall@10, latency analysis

---

#### **QPhu: RAG Framework Comparison** (`Week0304_QPhu_RAG_Pipeline/`)

Systematic evaluation of three RAG implementation approaches.

**Frameworks**:

1. **LangChain**: High-level abstractions, extensive integrations
2. **LlamaIndex**: Python-native, data-centric design
3. **Manual**: Custom implementation for full control

**Configuration Options**:

- **Vector Stores**: FAISS (in-memory), Chroma (persistent)
- **LLMs**: OpenAI GPT-4o-mini, Azure OpenAI, Google Gemini, Ollama
- **Benchmarking**: Automated metrics collection and reporting

**Use Case**: Comparative analysis for selecting optimal RAG stack

---

### 📅 **Week 05-06: Advanced Enhancements**

#### **MKhoi: Multi-Model ASR/OCR** (`Week0506_Mkhoi_OCR_ASR/`)

Expanded processing pipeline with multiple AI backends and detailed benchmarking.

**ASR Models**:

- **OpenAI Whisper**: Variants from `tiny` to `large-v3`
- **Google Gemini**: API-based with 2.0/2.5 Flash models
- **DeepSeek**: Alternative API provider

**OCR Enhancements**:

- Advanced preprocessing (OTSU, adaptive thresholding)
- Multi-language support (Vietnamese + English)
- PDF batch processing with Poppler integration

**Deliverables**: Model comparison reports (`asr rank.md`, `ocr rank.md`, `model comparison.md`)

---

#### **NKhoi: Production Retrieval Systems** (`Week0506_NKhoi_Retrieval/`)

Industrial-grade retrieval implementations using specialized tools.

**Upgrades**:

- **Milvus**: Vector database for billion-scale dense retrieval
- **Pyserini**: Lucene-based BM25 with advanced linguistic processing
- **ColPali**: Vision-language retrieval for document images (no OCR needed)

**Performance Improvements**:

- 44 minutes → ~10 seconds for BM25 (Pyserini)
- 6 seconds → <1 second for Dense (Milvus)
- Better tokenization, stemming, and query optimization

**Novel Approach**: ColPali for end-to-end visual retrieval (bypassing OCR errors)

---

### 📅 **Week 07-09: Production Pipeline**

#### **QPhu: Unified Processing Pipeline** (`Week070809_QPhu_Processor/`)

Complete overhaul into production-ready 4-stage pipeline with enterprise features and intelligent processing.

**Architecture Overview**:

- **Stage 1 (Normalizer)**: Format conversion with consistent filename truncation for Windows compatibility
- **Stage 2 (Media Processor)**: Audio/video transcription with multiple export formats (JSON/SRT/VTT/MD)
- **Stage 3 (Docling Processor)**: Smart deduplication avoiding duplicate processing, VLM-powered understanding
- **Stage 4 (Consolidator)**: RAG-ready unified structure with dual-mode outputs

**Core Features**:

- **Smart Deduplication**: Process each file only once, optimal quality source selection
- **Dual RAG Outputs**: Normalized PDFs for image retrieval + Markdown for semantic search
- **Universal Format Support**: 15+ formats (DOCX, PPTX, HTML, Images, Video, Audio, PDF, Excel, CSV, AsciiDoc, WebVTT)

**Advanced Capabilities**:

- **Visual Understanding**: SmolVLM-256M integration for image descriptions and layout analysis
- **Processing Modes**:
  - Full Mode (default): VLM-enabled, highest quality, ~1× speed
  - Balanced Mode (`--no-vlm`): OCR-only with exports, ~2× faster
  - Fast Mode (`--fast-mode`): OCR-only minimal exports, 3-5× faster
- **Intelligent Caching**: MD5-based skip system with `--force` flag to bypass
- **Windows Optimization**: Automatic filename truncation (50 chars + MD5 hash) for 260-char path limit
- **Multi-OCR Support**: RapidOCR (primary), Tesseract, EasyOCR
- **ASR Integration**: Whisper-based transcription for audio/video with configurable models

**Performance Optimizations**:

- GPU acceleration (CUDA support)
- Batch processing with progress tracking
- Exponential backoff retry mechanism
- Comprehensive error handling and logging
- Graceful degradation for unsupported formats

**Output Structure**:

```
stage4_rag_ready/
├── document_name.pdf                    # Image-based RAG (preserved layout)
├── document_name.md                     # Text-based RAG (semantic search)
└── document_name_docling_additional/    # Extracted images/tables
    ├── images/
    └── tables/
```

---

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.9+ (tested on 3.9, 3.10, 3.11)
- **GPU**: CUDA-compatible (recommended for ASR/Dense retrieval)
- **System Tools**:
  - FFmpeg (audio/video processing)
  - Tesseract OCR (slide text extraction)
  - Poppler (PDF conversion)

### Installation

```bash
# Clone repository
git clone https://github.com/pdz1804/capstone-project.git
cd capstone-project

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install dependencies (example: Week0304 RAG Pipeline)
cd Week0304_QPhu_RAG_Pipeline
pip install -r requirements.txt
```

### Running Components

```bash
# ASR/OCR Processing
cd Week0506_Mkhoi_OCR_ASR/src
python main.py asr --output-dir results/asr data/videos/*.mp4

# Retrieval Evaluation
cd Week0304_NKhoi_Retrieval
jupyter notebook manual_bm25_dense_hybrid.ipynb

# RAG Pipeline
cd Week0304_QPhu_RAG_Pipeline
python setup_and_run.py

# Production Document Processing (Week 07-09)
cd Week070809_QPhu_Processor
python src/pipeline.py input/ output/              # Full quality (VLM enabled)
python src/pipeline.py input/ output/ --fast-mode  # Fast mode (3-5x faster)
```

---

## 📊 Key Results & Benchmarks

### ASR Performance (Week 05-06)

- **Whisper Large-v3**: Best accuracy for Vietnamese (WER: ~8%)
- **Gemini 2.5 Flash**: Fastest API inference (<2s per minute of audio)
- **Chunking Strategy**: 30-second chunks with 1-second overlap

### Retrieval Performance (Week 03-04)

| Method                     | nDCG@10          | Recall@10        | Inference Time (1000 queries) |
| -------------------------- | ---------------- | ---------------- | ----------------------------- |
| BM25 (manual)              | 0.0663           | 0.1133           | 44 minutes                    |
| Dense (SBERT)              | **0.2411** | **0.3557** | 6 seconds                     |
| Milvus (Week 05-06)        | 0.2411           | 0.3557           | **<1 second**           |
| Pyserini BM25 (Week 05-06) | ~0.10            | ~0.18            | **~10 seconds**         |

### RAG Framework Comparison (Week 03-04)

- **LangChain**: Best for rapid prototyping, extensive ecosystem
- **LlamaIndex**: Superior data ingestion, Python-native
- **Manual**: Full control, minimal dependencies, optimal for research

### Document Processing Performance (Week 07-09)

| Mode                | VLM Enabled | Images/Tables Export | Relative Speed | Quality |
| ------------------- | ----------- | -------------------- | -------------- | ------- |
| Full (default)      | ✅ Yes      | ✅ Yes               | 1× (baseline) | Highest |
| Balanced (--no-vlm) | ❌ No       | ✅ Yes               | ~2× faster    | High    |
| Fast (--fast-mode)  | ❌ No       | ❌ No                | 3-5× faster   | Good    |

**Pipeline Features**:

- **Smart Caching**: Instant skip for already-processed files (100% speedup)
- **Format Support**: 15+ formats including DOCX, PPTX, HTML, Images, Video, Audio
- **Dual RAG Output**: Normalized PDFs (image retrieval) + Markdown (text search)
- **Windows-Safe**: Automatic filename truncation for 260-char path limit

---

## 🎓 Academic Context

**Course**: CS251 - Capstone Project
**Institution**: Ho Chi Minh City University of Technology (HCMUT)
**Focus**: Applied AI for Educational Content Processing
**Domain**: Information Retrieval, NLP, Multimodal Learning, RAG Systems

**Research Contributions**:

1. Vietnamese-optimized ASR/OCR pipeline for lecture processing
2. Comprehensive retrieval method comparison on MS MARCO
3. RAG framework selection guide for educational Q&A
4. Production-grade retrieval system implementations
5. Multimodal document understanding with Docling
6. Dual-mode RAG processing pipeline (text + image retrieval)
7. Intelligent document deduplication and caching system
8. Performance-quality tradeoff framework (Fast vs Full modes)

---

## 📚 Documentation

Each weekly component includes detailed READMEs with:

- Technical specifications and architecture
- Installation and setup instructions
- Usage examples and CLI documentation
- Performance benchmarks and evaluation metrics
- Troubleshooting guides and FAQs

**Specialized Documentation**:

- `DETAILED_PIPELINE_FLOWS.md` (Week0304 RAG): In-depth RAG architecture
- `model comparison.md` (Week0506 ASR/OCR): Multi-model benchmarking
- `asr rank.md`, `ocr rank.md`: Model-specific evaluations
- `README.md` (Week070809 Processor): Complete pipeline documentation with CLI reference
- `docs/ARCHITECTURE.md` (Week070809): Stage-by-stage processing flow diagrams

---

## 🔬 Research Papers & References

The `downloads/` directory contains a curated collection of research papers covering:

- Retrieval-Augmented Generation (RAG) architectures
- Dense retrieval methods (DPR, ColBERT, ANCE)
- Multimodal learning (CLIP, LayoutLM, Docling)
- Speech recognition (Whisper, Wav2Vec 2.0)
- OCR and document understanding

---

## 🤝 Contributing

This is an academic capstone project. For collaboration or questions:

- **Repository**: [github.com/pdz1804/capstone-project](https://github.com/pdz1804/capstone-project)
- **Issues**: Use GitHub Issues for bug reports or feature requests
- **Contact**: See individual weekly READMEs for team member information

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Quang Phu, Ngoc Khoi, and Minh Khoi

---

## 🙏 Acknowledgments

- **OpenAI**: Whisper ASR models
- **Google**: Gemini API, BERT embeddings
- **Hugging Face**: Transformers library, model hosting
- **IBM**: Docling framework
- **Pyserini/Anserini**: Lucene-based retrieval
- **Milvus**: Vector database infrastructure
- **LangChain & LlamaIndex**: RAG frameworks

---

**Last Updated**: November 23, 2025
**Project Status**: Production Ready (Week 07-09 Pipeline)
**Team**: MKhoi (ASR/OCR), NKhoi (Retrieval/Embeddings), QPhu (Pipeline/Integration)
**Latest Release**: Week 07-09 Unified Processing Pipeline v1.0
