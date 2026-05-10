# Unified Document Processing Pipeline for RAG

A comprehensive, production-ready document processing pipeline that normalizes, processes, and prepares multimodal documents for RAG (Retrieval-Augmented Generation) systems.

**Handles any document type**   DOCX, PPTX, PDF, HTML, Images, Excel, CSV, Video, Audio, AsciiDoc, WebVTT   and prepares them for both text-based and image-based RAG systems.

**Platform Support:** Windows | macOS | Linux
**Python Version:** 3.9+

## Overview

This pipeline handles any document type through a **four-stage architecture** optimized for dual-mode RAG (text-based + image-based retrieval):

```
┌─────────────────────────────────────────────────────────────┐
│     INPUT: DOCX, PPTX, HTML, XHTML, Images, Excel, CSV,    │
│       Video, Audio, PDF, Markdown, Text, AsciiDoc, WebVTT   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         STAGE 1: NORMALIZATION (normalizer.py)              │
│  • DOCX/PPTX/HTML/XHTML → PDF (for image-based RAG)         │
│  • Images (PNG/JPG/BMP/TIFF/WEBP) → PDF (for image RAG)     │
│  • TXT → Markdown (simple text files)                       │
│  • Copy ALL originals to original_files/ (for Docling)      │
│  • Note: NO markdown conversion for DOCX/PPTX/HTML/CSV      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│       STAGE 2: MEDIA PROCESSING (media_processor.py)        │
│  • Video → Audio → Text transcription (Whisper)             │
│  • Audio → Text transcription (Whisper)                     │
│  • Export: .json, .srt, .vtt, .txt, .md                     │
│  • Optional: Extract video frames for image retrieval       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│       STAGE 3: DOCLING PROCESSING (document_processor.py)   │
│  • SMART DEDUPLICATION: Process each file only ONCE         │
│  • Priority 1: Normalized PDFs (converted files)            │
│    - DOCX→PDF, PPTX→PDF, HTML→PDF, Images→PDF              │
│  • Priority 2: Original files NOT converted to PDF          │
│    - Only files that weren't in normalized_pdfs             │
│  • Priority 3: Markdown files (TXT→MD conversions)          │
│  • Priority 4: Transcripts (.md only, not .json/.srt/.vtt)  │
│  • Result: NO duplicate processing, optimal quality         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         STAGE 4: CONSOLIDATION (consolidator.py)            │
│  • Combine outputs into unified RAG-ready structure         │
│  • For each document:                                       │
│    - file.pdf (optional, from normalized_pdfs)              │
│    - file.md (required, from Docling output)                │
│    - docling_additional/ (optional, images/tables/etc)      │
│  • Output: stage4_rag_ready/                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   OUTPUTS FOR RAG                            │
│  📄 Text-based RAG: Unified markdown (file.md)               │
│  🖼️ Image-based RAG: Normalized PDFs (file.pdf)             │
│  📊 Additional: Images, tables in docling_additional/       │
└─────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Dual RAG Approach:**

- **Normalized PDFs** → Used for image-based retrieval (preserves visual layout)
- **Docling-processed Markdown** → Used for text-based semantic search
- **Original files** → Processed by Docling (better quality than re-processing PDFs)
- **Unified Structure** → Stage 4 consolidates everything into consistent RAG-ready format

**Key Principle:** Process ORIGINAL files through Docling for best text extraction quality, while keeping normalized PDFs separate for image-based RAG.

## 🔄 Processing Workflow

### Input Files → Processing → RAG Outputs

| Input Type          | Stage 1: Normalization   | Stage 2: Media   | Stage 3: Docling     | Stage 4: Consolidation | Final Output |
| ------------------- | ------------------------ | ---------------- | -------------------- | ---------------------- | ------------ |
| **DOCX/PPTX** | → PDF (image RAG)       | -                | Original → Markdown | Combine PDF + MD      | PDF + MD     |
| **HTML/XHTML** | → PDF (image RAG)       | -                | Original → Markdown | Combine PDF + MD      | PDF + MD     |
| **Images (PNG/JPG/BMP/TIFF/WEBP)** | → PDF (image RAG) | - | Original → Markdown | Combine PDF + MD | PDF + MD |
| **Excel/CSV** | ❌ NOT converted         | -                | ❌ CSV only          | Combine             | MD only      |
| **Video**     | -                        | → Audio → Text  | .md → Markdown      | Combine              | MD only      |
| **Audio**     | -                        | → Text          | .md → Markdown      | Combine              | MD only      |
| **PDF**       | ✅ Kept as-is            | -                | Original → Markdown | Combine PDF + MD      | PDF + MD     |
| **Markdown**  | ✅ Kept as-is            | -                | Process             | Combine              | MD only      |
| **AsciiDoc**  | ✅ Copy to originals     | -                | Process             | Combine              | MD only      |
| **Text**      | → Markdown              | -                | Process             | Combine              | MD only      |
| **WebVTT**    | ✅ Copy to originals     | -                | Process             | Combine              | MD only      |

**Key Changes from Previous Version:**

- **Stage 1**: NO longer converts DOCX/PPTX/HTML/CSV to markdown (only TXT→MD)
- **Stage 2**: NOW exports transcript.md alongside .json/.srt/.vtt/.txt
- **Stage 3**: Processes ALL 4 input sources: original_files/, normalized_pdfs/, normalized_markdown/, transcripts/*.md
- **Stage 4**: NEW - Consolidates into unified structure (file.pdf + file.md + docling_additional/)

## ✨ Key Features

### Universal Format Support

- **Documents**: DOCX, PPTX, ODT, RTF
- **Web**: HTML, MHTML, XHTML
- **Spreadsheets**: XLSX, XLS, CSV
- **Images**: PNG, JPG, JPEG, BMP, TIFF, WEBP
- **Media**: MP4, AVI, MOV, WAV, MP3, M4A
- **Markup**: Markdown, AsciiDoc (.adoc, .asciidoc, .asc)
- **Subtitles**: WebVTT (.vtt)
- **Already normalized**: PDF, TXT

### Advanced Processing

- **Intelligent Normalization**: Converts to PDF only (no markdown conversion)
- **Media Understanding**: Audio transcription (with markdown export) + frame extraction
- **Deep Document Analysis**: Docling-powered OCR, VLM, table extraction
- **GPU Acceleration**: CUDA support for faster processing
- **Unified Consolidation**: Consistent RAG-ready output structure
- **Robust Error Handling**: Detailed logging and error recovery

### RAG-Optimized Outputs

- **Text-based retrieval**: Clean unified markdown for semantic search
- **Image-based retrieval**: Processed PDFs with preserved visual layout
- **Hybrid approach**: Combine text and visual information
- **Metadata rich**: JSON files with structure and statistics
- **Organized structure**: file.pdf + file.md + docling_additional/ per document

## 📁 Project Structure

```
Week070809_QPhu_Processor/
├── requirements.txt             # Python dependencies
├── README.md                    # This file (updated architecture)
│
├── src/                         # Source code modules
│   ├── pipeline.py              # Main entry point - RUN THIS!
│   ├── normalizer.py            # Stage 1: PDF normalization only
│   ├── media_processor.py       # Stage 2: Video/Audio + MD export
│   ├── document_processor.py    # Stage 3: Docling processing
│   ├── consolidator.py          # Stage 4: RAG-ready consolidation
│   └── utils.py                 # Utility functions
│
├── input/                       # Place your raw files here
│
└── output/                      # Processing outputs (auto-created)
    ├── stage1_normalized/       # Stage 1 outputs
    │   ├── normalized_pdfs/     # PDF files for image-based RAG
    │   ├── normalized_markdown/ # TXT→MD files only
    │   ├── original_files/      # ALL original files (for Docling)
    │   └── normalization_metadata/
    │
    ├── stage2_media_processed/  # Stage 2 outputs
    │   ├── audio/               # Extracted audio files
    │   ├── transcripts/         # Text transcriptions (.json/.srt/.vtt/.txt/.md)
    │   ├── frames/              # Extracted video frames
    │   └── media_metadata/
    │
    ├── stage3_document_processed/ # Stage 3 outputs
    │   ├── {filename}/          # Per-document folder
    │   │   ├── {filename}.md    # Docling markdown
    │   │   ├── {filename}_metadata.json
    │   │   ├── images/          # Extracted images
    │   │   └── tables/          # Extracted tables
    │   └── logs/
    │
    ├── stage4_rag_ready/        # Stage 4: Final RAG-ready outputs
    │   ├── {document_name}/     # Per-document folder
    │   │   ├── {document_name}.pdf          # Optional: normalized PDF
    │   │   ├── {document_name}.md           # Required: unified markdown
    │   │   └── docling_additional/          # Optional: extra files
    │   │       ├── images/                  # Extracted images
    │   │       ├── tables/                  # Extracted tables
    │   │       └── {document_name}_metadata.json
    │   └── consolidation.log
    │
    └── pipeline_stats.json      # Overall processing statistics
```

## Quick Start (2 Minutes)

```bash
# 1. Clone or download this repository
git clone <your-repo-url>
cd Week070809_QPhu_Processor

# 2. Create virtual environment and install Python packages
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# 3. Install LibreOffice (for DOCX/PPTX with images)
# Windows: Download from https://www.libreoffice.org/download/
# Linux: sudo apt-get install libreoffice
# Mac: brew install libreoffice

# 4. Put your files in input/ folder and run!
python src/pipeline.py input/ output/
```

**That's it!** Your documents are now processed and ready for RAG in `output/stage4_rag_ready/`.

---

## Detailed Installation

### 1. Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Install Python dependencies
pip install -r requirements.txt
```

### 2. System Dependencies

Install these based on your needs:

**Windows:**

- **LibreOffice** (Required for DOCX/PPTX → PDF with images): https://www.libreoffice.org/download/
- **FFmpeg** (Required for video/audio processing): https://ffmpeg.org/download.html
- **Tesseract OCR** (Optional, for enhanced OCR): https://github.com/UB-Mannheim/tesseract/wiki

**Linux (Ubuntu/Debian):**

```bash
# Required dependencies
sudo apt-get update
sudo apt-get install -y libreoffice ffmpeg tesseract-ocr

# Optional: Additional language packs for Tesseract
sudo apt-get install -y tesseract-ocr-eng tesseract-ocr-vie
```

**Mac:**

```bash
# Using Homebrew
brew install libreoffice ffmpeg tesseract

# Or download LibreOffice: https://www.libreoffice.org/download/
```

## Usage

### Basic Usage

```bash
# Process all files in input/ directory
python src/pipeline.py input/ output/
```

The pipeline will:

1. ✅ Normalize documents to PDF only (no markdown conversion)
2. ✅ Extract and transcribe audio from videos (export .md format)
3. ✅ Process ALL files through Docling (originals + normalized PDFs + transcripts)
4. ✅ Consolidate into unified RAG-ready structure

### Advanced Usage

```bash
# Skip normalization (files already normalized)
python src/pipeline.py input/ output/ --skip-normalization

# Process only video/audio files
python src/pipeline.py input/ output/ --media-only

# Use CPU instead of GPU
python src/pipeline.py input/ output/ --no-gpu

# Use larger Whisper model for better transcription
python src/pipeline.py input/ output/ --asr-model large-v3

# Extract frames every 50 frames instead of 100
python src/pipeline.py input/ output/ --frame-interval 50

# Don't extract video frames (faster, no image retrieval)
python src/pipeline.py input/ output/ --no-frames

# Fast mode: Disable VLM, skip images/tables export (much faster)
python src/pipeline.py input/ output/ --fast-mode

# Disable VLM only (keep images/tables export)
python src/pipeline.py input/ output/ --no-vlm

# Export images from documents (enabled by default)
python src/pipeline.py input/ output/ --export-images

# Export tables from documents (enabled by default)
python src/pipeline.py input/ output/ --export-tables

# Force reprocess all files (ignore cache)
python src/pipeline.py input/ output/ --force
```

### Processing Modes

**🚀 Fast Mode (Recommended for development/testing)**
```bash
# Fastest processing: OCR-only, no VLM, no images/tables export
python src/pipeline.py input/ output/ --fast-mode
```
- ⚡ **3-5x faster** than full mode
- ✅ All text content extracted
- ✅ Tables inline in markdown
- ❌ No VLM image descriptions
- ❌ No separate image/table files

**🎯 Balanced Mode (Default)**
```bash
# Default: VLM enabled, images/tables exported
python src/pipeline.py input/ output/
```
- 🎨 **VLM image descriptions** (SmolVLM-256M)
- ✅ All text + structure extracted
- ✅ Images and tables exported separately
- ⏱️ Slower but highest quality

**🔧 Custom Mode**
```bash
# OCR-only but with images/tables export
python src/pipeline.py input/ output/ --no-vlm

# VLM enabled but skip images/tables export (for markdown-only RAG)
python src/pipeline.py input/ output/ --no-export-images --no-export-tables
```

## 🎓 Python API Usage

### Full Pipeline

```python
from pipeline import DocumentProcessingPipeline, PipelineConfig

# Create configuration
config = PipelineConfig(
    enable_normalization=True,
    enable_media_processing=True,
    enable_document_processing=True,
    use_gpu=True
)

# Run pipeline (includes all 4 stages)
pipeline = DocumentProcessingPipeline(
    input_dir="input",
    output_dir="output",
    config=config
)

stats = pipeline.run()
print(f"RAG-ready files: {stats['stages']['consolidation']['total_documents']}")
```

### Individual Stages

#### Stage 1: Normalization Only

```python
from src.normalizer import DocumentNormalizer, NormalizerConfig

config = NormalizerConfig(
    generate_pdf=True,           # Create PDFs for image RAG
    generate_markdown=False,     # NO markdown conversion (except TXT)
    image_to_pdf=True,           # Convert images to PDF
    excel_to_markdown=False,     # NO Excel→MD conversion
    csv_to_markdown=False        # NO CSV→MD conversion
)

normalizer = DocumentNormalizer("input", "output/normalized", config)
stats = normalizer.normalize_batch()
```

#### Stage 2: Media Processing Only

```python
from src.media_processor import MediaProcessor, MediaProcessorConfig

config = MediaProcessorConfig(
    extract_audio=True,
    enable_transcription=True,
    asr_model="base",
    extract_frames=True,
    export_txt=True,
    export_json=True,
    export_srt=True,
    export_vtt=True,
    export_markdown=True         # NEW: Export .md format
)

processor = MediaProcessor("input/videos", "output/media", config)
stats = processor.process_batch()
```

#### Stage 3: Document Processing Only

```python
from src.document_processor import MultimodalDocumentProcessor, ProcessingConfig

config = ProcessingConfig(
    use_gpu=True,
    enable_ocr=True,
    enable_vlm=True,      # Enable VLM for image descriptions (slower)
    export_markdown=True,
    export_images=True,   # Export images to docling_additional/
    export_tables=True    # Export tables to docling_additional/
)

# For fast processing, disable VLM:
# config.enable_vlm = False

# Stage 3 processes from 4 sources:
# 1. original_files/ (best quality)
# 2. normalized_pdfs/ (may have better OCR)
# 3. normalized_markdown/ (existing MD files)
# 4. transcripts/*.md (video/audio transcripts)

processor = MultimodalDocumentProcessor("input", "output/docs", config)
stats = processor.process_batch()
```

#### Stage 4: Consolidation Only

```python
from src.consolidator import Stage4Consolidator, ConsolidatorConfig

config = ConsolidatorConfig()

consolidator = Stage4Consolidator(
    stage1_dir="output/stage1_normalized",
    stage3_dir="output/stage3_document_processed",
    output_dir="output/stage4_rag_ready",
    config=config
)

stats = consolidator.consolidate()
print(f"Documents: {stats['total_documents']}")
print(f"With PDF: {stats['with_pdf']}")
print(f"With Markdown: {stats['with_markdown']}")
```

## 📊 Output Structure

After processing, your output directory will contain:

```
output/
├── stage1_normalized/
│   ├── normalized_pdfs/         # PDFs for IMAGE-BASED RAG
│   │   ├── document1.pdf        # DOCX → PDF (LibreOffice)
│   │   ├── presentation1.pdf    # PPTX → PDF (LibreOffice)
│   │   ├── webpage1.pdf         # HTML → PDF (LibreOffice)
│   │   └── image1.pdf           # PNG/JPG → PDF (Pillow)
│   ├── normalized_markdown/     # TXT → MD only (NO other conversions)
│   │   └── text_file.md         # TXT → Markdown
│   ├── original_files/          # ALL originals (for Docling Stage 3)
│   │   ├── document1.docx       # Original DOCX
│   │   ├── presentation1.pptx   # Original PPTX
│   │   ├── webpage1.html        # Original HTML
│   │   ├── spreadsheet1.xlsx    # Original Excel
│   │   ├── data.csv             # Original CSV
│   │   ├── diagram.png          # Original image
│   │   └── notes.md             # Original markdown
│   └── normalization_metadata/
│
├── stage2_media_processed/
│   ├── audio/                   # Extracted audio (.wav)
│   ├── transcripts/             # NEW: Includes .md format!
│   │   ├── video1.json          # Full Whisper output
│   │   ├── video1.srt           # SRT subtitles
│   │   ├── video1.vtt           # WebVTT subtitles
│   │   ├── video1.txt           # Plain text
│   │   └── video1.md            # Markdown with timestamps (NEW!)
│   ├── frames/                  # Video frames (optional)
│   └── media_metadata/
│
├── stage3_document_processed/   # Docling outputs (from 4 sources)
│   ├── document1/               # From original_files/document1.docx
│   │   ├── document1.md         # Docling markdown (high quality)
│   │   ├── document1_metadata.json
│   │   ├── images/
│   │   └── tables/
│   ├── document1_normalized/    # From normalized_pdfs/document1.pdf
│   │   └── document1_normalized.md  # May have better OCR
│   ├── video1/                  # From transcripts/video1.md
│   │   └── video1.md            # Processed transcript
│   └── logs/
│
├── stage4_rag_ready/            # 🎯 FINAL RAG-READY OUTPUTS
│   ├── document1/               # Consolidated document
│   │   ├── document1.pdf        # ← From stage1/normalized_pdfs/
│   │   ├── document1.md         # ← From stage3 (best version)
│   │   └── docling_additional/  # ← From stage3
│   │       ├── images/
│   │       ├── tables/
│   │       └── document1_metadata.json
│   ├── video1/                  # Video transcript (no PDF)
│   │   └── video1.md
│   └── consolidation.log
│
└── pipeline_stats.json
```

### Understanding the Stage 4 RAG-Ready Output

**For RAG Systems, USE THIS DIRECTORY:** `output/stage4_rag_ready/`

Each document folder contains:

- **file.pdf** (optional): Normalized PDF for image-based RAG (ColPali, ColQwen)
- **file.md** (required): Unified markdown for text-based RAG (BM25, Dense, Hybrid)
- **docling_additional/** (optional): Supplementary files (images, tables, metadata)

**Benefits:**

- ✅ Consistent structure across all document types
- ✅ Easy to integrate with RAG pipelines (just point to stage4_rag_ready/)
- ✅ Both PDF and Markdown available in single location
- ✅ No need to navigate multiple stage directories

## 🔧 Configuration Options

### Pipeline Configuration

```python
PipelineConfig(
    enable_normalization=True,      # Run Stage 1 (PDF normalization)
    enable_media_processing=True,   # Run Stage 2 (video/audio → text)
    enable_document_processing=True, # Run Stage 3 (Docling processing)
    # Stage 4 (consolidation) always runs if Stage 3 completes
    use_gpu=True,                   # Enable GPU acceleration
    keep_intermediate_files=True,   # Keep stage1/stage2/stage3 files
    skip_processed=True             # Skip already-processed files (cache)
)
```

### Normalizer Configuration

```python
NormalizerConfig(
    generate_pdf=True,              # Create PDFs for image RAG
    generate_markdown=False,        # NO markdown (except TXT→MD)
    image_to_pdf=True,              # Convert PNG/JPG/WEBP to PDF
    excel_to_markdown=False,        # NO Excel→MD conversion
    csv_to_markdown=False,          # NO CSV→MD conversion
    pdf_page_size="A4"              # PDF page size
)
```

### Media Processor Configuration

```python
MediaProcessorConfig(
    extract_audio=True,
    enable_transcription=True,
    asr_model="base",               # tiny/base/small/medium/large/large-v3
    extract_frames=True,
    frame_interval=100,
    export_txt=True,
    export_json=True,
    export_srt=True,
    export_vtt=True,
    export_markdown=True            # NEW: Export .md format
)
```

### Document Processor Configuration

```python
ProcessingConfig(
    use_gpu=True,
    enable_ocr=True,
    enable_vlm=True,                # 🎨 VLM for image descriptions (slower but better)
    enable_asr=False,               # Audio handled in Stage 2
    export_markdown=True,
    export_images=True,             # ✅ Enabled by default - extracts images to docling_additional/
    export_tables=True,             # ✅ Enabled by default - extracts tables to docling_additional/
    export_metadata=True
)
```

**Processing Modes:**
- **Full Mode** (default): `enable_vlm=True` - Uses SmolVLM-256M for image descriptions, slower but highest quality
- **Fast Mode**: `enable_vlm=False` - OCR-only processing, 3-5x faster, still extracts all text/tables
- **Note**: Images/tables export adds processing time but provides separate files in `docling_additional/`

### Consolidator Configuration

```python
ConsolidatorConfig(
    copy_pdfs=True,                 # Copy normalized PDFs
    include_additional_files=True   # Include images/tables
)
```

## 🚢 Deployment Guide

### System Dependencies Summary

| Dependency              | Purpose                      | Required?                    | Installation             |
| ----------------------- | ---------------------------- | ---------------------------- | ------------------------ |
| **LibreOffice**   | DOCX/PPTX → PDF with images | **Recommended**        | System package (not pip) |
| **FFmpeg**        | Video/Audio processing       | **Required** for media | System package           |
| **Tesseract OCR** | Enhanced OCR                 | Optional                     | System package           |
| **Python 3.9+**   | Runtime                      | **Required**           | Standard Python          |

### Cross-Platform Compatibility

**✅ Windows:**

- LibreOffice: Auto-detected in `C:\Program Files\LibreOffice\`
- Works with silent background execution

**✅ macOS:**

- LibreOffice: Auto-detected in `/Applications/LibreOffice.app/`

**✅ Linux:**

- LibreOffice: Auto-detected in `/usr/bin/soffice`

## 🎯 Use Cases

### 1. Educational Content Processing

```bash
# Process lecture slides + videos + transcripts
python pipeline.py lectures/ processed_lectures/ --asr-model large-v3
# Output: stage4_rag_ready/ with PDFs + unified markdown
```

### 2. Document Archive Digitization

```bash
# Process scanned PDFs and images with OCR
python pipeline.py archive/ digitized/
# Output: stage4_rag_ready/ with PDFs + markdown
```

### 3. Video Content Analysis

```bash
# Extract transcripts and frames from videos
python pipeline.py videos/ analyzed/ --frame-interval 50
# Output: stage4_rag_ready/ with markdown transcripts
```

### 4. Mixed Document Collection

```bash
# Process everything: docs, images, videos, spreadsheets
python pipeline.py mixed_content/ processed/
# Output: stage4_rag_ready/ with unified structure
```

## 🔄 Key Changes from Previous Version

### Stage 1: Normalization

**OLD:**

- ✅ DOCX → PDF (LibreOffice)
- ✅ DOCX → Markdown (python-docx)
- ✅ PPTX → PDF (LibreOffice)
- ✅ PPTX → Markdown (python-pptx)
- ✅ HTML → Markdown (BeautifulSoup)
- ✅ Excel → Markdown (openpyxl)
- ✅ CSV → Markdown (pandas)

**NEW:**

- ✅ DOCX → PDF (LibreOffice) **ONLY**
- ❌ NO DOCX → Markdown
- ✅ PPTX → PDF (LibreOffice) **ONLY**
- ❌ NO PPTX → Markdown
- ✅ HTML/XHTML → PDF (LibreOffice) **ONLY**
- ❌ NO HTML → Markdown
- ❌ NO Excel → Markdown
- ❌ NO CSV → Markdown
- ✅ TXT → Markdown (NEW, simple text files)
- ✅ Copy ALL files to original_files/ (for Docling)
- ✅ Support WEBP, XHTML, AsciiDoc, WebVTT (NEW formats)

**Reasoning:** Let Docling handle markdown conversion for better quality. Stage 1 focuses on PDF creation for image-based RAG only.

### Stage 2: Media Processing

**OLD:**

- ✅ Video → Audio → Transcription
- ✅ Export formats: .json, .srt, .vtt, .txt

**NEW:**

- ✅ Video → Audio → Transcription
- ✅ Export formats: .json, .srt, .vtt, .txt, **.md** (NEW!)
- ✅ Markdown format includes readable timestamps (HH:MM:SS)

**Reasoning:** Export .md format so transcripts can be processed by Docling in Stage 3.

### Stage 3: Document Processing

**OLD:**

- ✅ Process from: original_files/, normalized_markdown/, transcripts/
- ✅ Docling processes all supported formats

**NEW:**

- ✅ Process from **4 sources**:
  1. original_files/ (best quality)
  2. normalized_pdfs/ (may have better OCR) **NEW!**
  3. normalized_markdown/ (existing MD/TXT files)
  4. transcripts/\*.md **only** (filtered .json/.srt/.vtt/.txt)
- ✅ Added format support: WEBP, XHTML, CSV, AsciiDoc, WebVTT

**Reasoning:** Process normalized PDFs for potential OCR improvements. Filter transcript files to avoid duplicates.

### Stage 4: Consolidation (NEW!)

**NEW STAGE:**

- ✅ Consolidate outputs into unified RAG-ready structure
- ✅ For each document:
  - file.pdf (from stage1/normalized_pdfs/)
  - file.md (from stage3, best version)
  - docling_additional/ (images, tables, metadata)
- ✅ Output directory: stage4_rag_ready/

**Reasoning:** Provide consistent, easy-to-use output structure for RAG pipelines.

---

## Summary of Pipeline Flow

```
INPUT FILES
    ↓
STAGE 1: Create PDFs for image RAG + copy originals
    ↓
STAGE 2: Transcribe media (export .md)
    ↓
STAGE 3: Process ALL files through Docling
         (originals + normalized PDFs + markdown + transcripts.md)
    ↓
STAGE 4: Consolidate into unified RAG-ready structure
         (file.pdf + file.md + docling_additional/)
    ↓
RAG-READY OUTPUT
```

**Final output location:** `output/stage4_rag_ready/`

---

**Happy Processing! 🎉**
