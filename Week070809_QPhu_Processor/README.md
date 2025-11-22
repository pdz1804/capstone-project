# Unified Document Processing Pipeline for RAG

A comprehensive, production-ready document processing pipeline that normalizes, processes, and prepares multimodal documents for RAG (Retrieval-Augmented Generation) systems.

**Handles any document type** — DOCX, PPTX, PDF, HTML, Images, Excel, CSV, Video, Audio — and prepares them for both text-based and image-based RAG systems.

**Platform Support:** Windows | macOS | Linux  
**Python Version:** 3.9+

## Overview

This pipeline handles any document type through a three-stage architecture optimized for dual-mode RAG (text-based + image-based retrieval):

```
┌─────────────────────────────────────────────────────────────┐
│        INPUT: DOCX, PPTX, HTML, Images, Excel, CSV,        │
│              Video, Audio, PDF, Markdown, Text              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         STAGE 1: NORMALIZATION (normalizer.py)              │
│  • DOCX/PPTX/HTML → PDF (for image-based RAG)               │
│  • Images → PDF (for image-based RAG)                       │
│  • Excel/CSV → Markdown (not processed by Docling)          │
│  • Keep originals for Docling processing                    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│       STAGE 2: MEDIA PROCESSING (media_processor.py)        │
│  • Video → Audio → Text transcription (Whisper)             │
│  • Audio → Text transcription (Whisper)                     │
│  • Optional: Extract video frames for image retrieval       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│       STAGE 3: DOCLING PROCESSING (document_processor.py)   │
│  • Original DOCX/PPTX/HTML/Images → Markdown (Docling)      │
│  • Transcribed text → Markdown (Docling)                    │
│  • Note: Process originals, NOT normalized PDFs             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   OUTPUTS FOR RAG                            │
│  📄 Text-based RAG: Docling-processed markdown               │
│  🖼️ Image-based RAG: Normalized PDFs + extracted images     │
│  📊 Structured data: JSON metadata, tables                  │
└─────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Dual RAG Approach:**
- **Normalized PDFs** → Used for image-based retrieval (preserves visual layout)
- **Docling-processed Markdown** → Used for text-based semantic search
- **Original files** → Processed by Docling (better quality than re-processing PDFs)

## 🔄 Processing Workflow

### Input Files → Processing → RAG Outputs

| Input Type | Stage 1: Normalization | Stage 2: Media | Stage 3: Docling | Output for RAG |
|-----------|------------------------|----------------|------------------|----------------|
| **DOCX/PPTX** | → PDF (image-based RAG) | - | Original → Markdown | PDF + Markdown |
| **HTML** | → PDF (image-based RAG) | - | Original → Markdown | PDF + Markdown |
| **Images** | → PDF (image-based RAG) | - | Original → Markdown | PDF + Markdown |
| **Excel/CSV** | → Markdown (stored) | - | ❌ Not processed | Markdown only |
| **Video** | - | → Audio → Text | Text → Markdown | Markdown |
| **Audio** | - | → Text | Text → Markdown | Markdown |
| **PDF** | ✅ Kept as-is | - | Original → Markdown | PDF + Markdown |
| **Markdown** | ✅ Kept as-is | - | Original → Markdown | Markdown |

**Key Insight**: We create PDFs for image-based RAG, but process ORIGINAL files (not PDFs) through Docling for better text extraction quality!

## ✨ Key Features

### Universal Format Support
- **Documents**: DOCX, PPTX, ODT, RTF
- **Web**: HTML, MHTML
- **Spreadsheets**: XLSX, XLS, CSV
- **Images**: PNG, JPG, JPEG, BMP, TIFF
- **Media**: MP4, AVI, MOV, WAV, MP3, M4A
- **Already normalized**: PDF, MD, TXT

### Advanced Processing
- **Intelligent Normalization**: Converts everything to PDF/Markdown
- **Media Understanding**: Audio transcription + frame extraction
- **Deep Document Analysis**: Docling-powered OCR, VLM, table extraction
- **GPU Acceleration**: CUDA support for faster processing
- **Robust Error Handling**: Detailed logging and error recovery

### RAG-Optimized Outputs
- **Text-based retrieval**: Clean markdown for semantic search
- **Image-based retrieval**: Processed PDFs and extracted images
- **Hybrid approach**: Combine text and visual information
- **Metadata rich**: JSON files with structure and statistics

## 📁 Project Structure

```
Week070809_QPhu_Processor/
├── pipeline.py                  # Main entry point - RUN THIS!
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── src/                         # Source code modules
│   ├── normalizer.py            # Stage 1: Format normalization
│   ├── media_processor.py       # Stage 2: Video/Audio processing
│   ├── document_processor.py    # Stage 3: Docling-based processing
│   └── utils.py                 # Utility functions
│
├── input/                       # Place your raw files here
│
└── output/                      # Processing outputs (auto-created)
    ├── stage1_normalized/       # Normalized PDFs and Markdown
    │   ├── normalized_pdfs/     # PDF files for image-based RAG
    │   ├── normalized_markdown/ # Quick preview markdown
    │   ├── docling_originals/   # Original files for Docling
    │   └── normalization_metadata/
    │
    ├── stage2_media_processed/  # Media processing outputs
    │   ├── audio/               # Extracted audio files
    │   ├── transcripts/         # Text transcriptions
    │   ├── frames/              # Extracted video frames
    │   └── media_metadata/
    │
    ├── stage3_document_processed/ # Final RAG-ready documents
    │   ├── {filename}/          # Per-document folder
    │   │   ├── {filename}.md    # Markdown for text-based RAG
    │   │   ├── {filename}_metadata.json
    │   │   ├── images/          # Extracted images
    │   │   └── tables/          # Extracted tables (CSV/MD)
    │   └── logs/
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
python pipeline.py input/ output/
```

**That's it!** Your documents are now processed and ready for RAG.

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

**AWS Lambda / Serverless Deployment:**

For serverless environments (AWS Lambda, Google Cloud Functions, etc.), you have two options:

1. **Use LibreOffice Layer** (Recommended for Lambda):
   ```bash
   # Use pre-built LibreOffice layer for AWS Lambda
   # See: https://github.com/shelfio/libreoffice-lambda-layer
   # Add layer ARN to your Lambda function
   ```

2. **Install in Docker container**:
   ```dockerfile
   FROM public.ecr.aws/lambda/python:3.11
   
   # Install LibreOffice
   RUN yum install -y wget tar gzip
   RUN wget https://downloadarchive.documentfoundation.org/libreoffice/old/7.6.4.1/rpm/x86_64/LibreOffice_7.6.4.1_Linux_x86-64_rpm.tar.gz
   RUN tar -xf LibreOffice_7.6.4.1_Linux_x86-64_rpm.tar.gz
   RUN cd LibreOffice_7.6.4.1_Linux_x86-64_rpm/RPMS && yum install -y *.rpm
   
   # Install FFmpeg
   RUN yum install -y ffmpeg
   
   # Copy application code
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY src/ ./src/
   ```

**Note on LibreOffice:**
- **Required for**: DOCX/PPTX → PDF conversion with preserved images
- **Fallback behavior**: If LibreOffice not found, pipeline uses ReportLab (text-only PDFs, no images)
- **Detection**: Automatic cross-platform detection (Windows/Mac/Linux)
- **No Python package**: LibreOffice is a system-level application, not a pip package

### Basic Usage

```bash
# Process all files in input/ directory
python src/pipeline.py input/ output/
```

That's it! The pipeline will:
1. ✅ Normalize all documents to PDF/Markdown
2. ✅ Extract and transcribe audio from videos
3. ✅ Process everything with Docling for RAG

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
```

## 🎓 Python API Usage

### Full Pipeline

```python
from src.pipeline import DocumentProcessingPipeline, PipelineConfig

# Create configuration
config = PipelineConfig(
    enable_normalization=True,
    enable_media_processing=True,
    enable_document_processing=True,
    use_gpu=True
)

# Run pipeline
pipeline = DocumentProcessingPipeline(
    input_dir="input",
    output_dir="output",
    config=config
)

stats = pipeline.run()
print(f"Processed {stats['total_output_files']} files")
```

### Individual Stages

#### Stage 1: Normalization Only

```python
from src.normalizer import DocumentNormalizer, NormalizerConfig

config = NormalizerConfig(
    generate_pdf=True,
    generate_markdown=True,
    excel_to_markdown=True
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
    extract_frames=True
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
    enable_vlm=True,
    export_markdown=True
)

processor = MultimodalDocumentProcessor("input/pdfs", "output/docs", config)
stats = processor.process_batch()
```

## 📊 Output Structure

After processing, your output directory will contain:

```
output/
├── stage1_normalized/
│   ├── normalized_pdfs/         # PDFs for IMAGE-BASED RAG retrieval
│   │   ├── document1.pdf        # Original DOCX → PDF
│   │   ├── presentation1.pdf    # Original PPTX → PDF
│   │   └── image1.pdf           # Original PNG → PDF
│   ├── normalized_markdown/     # Markdown files (Excel/CSV only)
│   │   └── spreadsheet1.md      # Excel → Markdown table
│   ├── normalization_metadata/  # Processing statistics
│   └── normalization.log
│
├── stage2_media_processed/
│   ├── extracted_audio/         # Audio files from videos (.wav)
│   ├── transcripts/            # Transcriptions (.txt, .json, .srt, .vtt)
│   │   ├── video1.txt           # Plain text transcript
│   │   ├── video1.json          # Full Whisper output with timestamps
│   │   ├── video1.srt           # SRT subtitles
│   │   └── video1.vtt           # WebVTT subtitles
│   ├── extracted_frames/       # Video frames for image retrieval (optional)
│   ├── media_metadata/         # Processing statistics
│   └── media_processing.log
│
├── stage3_document_processed/  # Docling-processed outputs for TEXT-BASED RAG
│   ├── [document_name]/        # One folder per ORIGINAL document
│   │   ├── [document_name].md  # Docling markdown (text-based RAG)
│   │   ├── [document_name]_metadata.json
│   │   ├── images/             # Extracted images from document
│   │   └── tables/             # Extracted tables (.csv, .md)
│   ├── [transcript_name]/      # Transcripts also processed by Docling
│   │   └── [transcript_name].md # Cleaned transcript markdown
│   └── logs/
│
├── pipeline_stats.json          # Overall pipeline statistics
└── pipeline_[timestamp].log     # Detailed execution log
```

### Understanding the Outputs

**For RAG Systems:**
- **Image-Based Retrieval**: Use `stage1_normalized/normalized_pdfs/` → ColPali, ColQwen, etc.
- **Text-Based Retrieval**: Use `stage3_document_processed/*/[name].md` → Dense/BM25/Hybrid embedding
- **Hybrid Approach**: Combine both for best results

**Key Points:**
- Stage 1 creates PDFs preserving visual layout (charts, diagrams, formatting)
- Stage 3 processes ORIGINAL files (not PDFs) through Docling for cleaner text extraction
- Transcripts go through Docling for consistent markdown formatting

## 🔧 Configuration Options

### Pipeline Configuration

```python
PipelineConfig(
    enable_normalization=True,      # Run Stage 1
    enable_media_processing=True,   # Run Stage 2
    enable_document_processing=True, # Run Stage 3
    use_gpu=True,                   # Enable GPU acceleration
    keep_intermediate_files=True    # Keep normalized files
)
```

### Normalizer Configuration

```python
NormalizerConfig(
    generate_pdf=True,              # Create PDFs for image retrieval
    generate_markdown=True,         # Create markdown for text retrieval
    image_to_pdf=True,              # Convert images to PDF
    excel_to_markdown=True,         # Convert Excel to markdown tables
    csv_to_markdown=True,           # Convert CSV to markdown tables
    max_table_rows=1000,            # Max rows in markdown tables
    pdf_page_size="A4"              # PDF page size
)
```

### Media Processor Configuration

```python
MediaProcessorConfig(
    extract_audio=True,             # Extract audio from video
    enable_transcription=True,      # Transcribe audio to text
    asr_model="base",               # Whisper model: tiny/base/small/medium/large
    audio_sample_rate=16000,        # Audio sample rate
    extract_frames=True,            # Extract frames from video
    frame_interval=100,             # Extract every Nth frame
    min_frame_quality=0.5,          # Skip blurry frames
    export_txt=True,                # Export plain text transcript
    export_json=True,               # Export JSON with timestamps
    export_srt=True,                # Export SRT subtitles
    export_vtt=True                 # Export WebVTT subtitles
)
```

### Document Processor Configuration

```python
ProcessingConfig(
    use_gpu=True,                   # Use GPU for processing
    enable_ocr=True,                # Enable OCR for scanned docs
    enable_vlm=True,                # Enable Visual Language Model
    enable_asr=False,               # Enable audio processing
    ocr_engine="rapidocr",          # OCR engine: tesseract/easyocr/rapidocr
    export_markdown=True,           # Export to markdown
    export_images=True,             # Extract images
    export_tables=True,             # Extract tables
    export_metadata=True,           # Export metadata JSON
    min_image_width=100,            # Filter small images
    min_image_height=100,           # Filter small images
    min_image_area=10000            # Filter by total area
)
```

## 🚢 Deployment Guide

### System Dependencies Summary

| Dependency | Purpose | Required? | Installation |
|-----------|---------|-----------|--------------|
| **LibreOffice** | DOCX/PPTX → PDF with images | **Recommended** | System package (not pip) |
| **FFmpeg** | Video/Audio processing | **Required** for media | System package |
| **Tesseract OCR** | Enhanced OCR | Optional | System package |
| **Python 3.9+** | Runtime | **Required** | Standard Python |

### Cross-Platform Compatibility

**✅ Windows:**
- LibreOffice: Auto-detected in `C:\Program Files\LibreOffice\`
- Works with silent background execution (no console popups)

**✅ macOS:**
- LibreOffice: Auto-detected in `/Applications/LibreOffice.app/`
- Works with standard LibreOffice installation

**✅ Linux (Ubuntu/Debian/CentOS):**
- LibreOffice: Auto-detected in `/usr/bin/soffice` or `/usr/local/bin/soffice`
- Install via: `apt-get install libreoffice` or `yum install libreoffice`

**⚠️ AWS Lambda / Serverless:**
- **Option 1**: Use LibreOffice Lambda Layer (https://github.com/shelfio/libreoffice-lambda-layer)
- **Option 2**: Docker container with LibreOffice installed (see Dockerfile example above)
- **Option 3**: Accept fallback to ReportLab (text-only PDFs, no images)

### Fallback Behavior

**If LibreOffice NOT installed:**
```
DOCX/PPTX Processing:
├─ ✓ Extracts text content
├─ ✓ Converts to Markdown
├─ ⚠️ PDF created with ReportLab (text-only, NO images)
└─ ℹ️ Message: "LibreOffice not found, using ReportLab (text-only)"
```

**If LibreOffice IS installed:**
```
DOCX/PPTX Processing:
├─ ✓ Extracts text content
├─ ✓ Converts to Markdown
├─ ✓ PDF created with LibreOffice (preserves images, formatting)
└─ ℹ️ Message: "LibreOffice conversion successful (images preserved)"
```

### Docker Deployment Example

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    ffmpeg \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create input/output directories
RUN mkdir -p input output

# Run pipeline
CMD ["python", "src/pipeline.py", "input/", "output/"]
```

### Environment Variables (Optional)

```bash
# Force LibreOffice path (override auto-detection)
export SOFFICE_PATH="/custom/path/to/soffice"

# Disable GPU (for CPU-only environments)
export USE_GPU=false

# Set Whisper model size
export WHISPER_MODEL=base
```

### Production Checklist

- [ ] LibreOffice installed (or accept text-only fallback)
- [ ] FFmpeg installed (if processing video/audio)
- [ ] Sufficient disk space (videos can be large)
- [ ] GPU available (optional, for faster processing)
- [ ] Firewall allows outbound connections (for model downloads)
- [ ] Write permissions for output directory

## 🎯 Use Cases

### 1. Educational Content Processing
```bash
# Process lecture slides, videos, and transcripts
python src/pipeline.py lectures/ processed_lectures/ --asr-model large-v3
```

### 2. Document Archive Digitization
```bash
# Process scanned PDFs and images with OCR
python src/pipeline.py archive/ digitized/ --skip-media
```

### 3. Video Content Analysis
```bash
# Extract transcripts and frames from videos
python src/pipeline.py videos/ analyzed/ --media-only --frame-interval 50
```

### 4. Mixed Document Collection
```bash
# Process everything: docs, images, videos, spreadsheets
python src/pipeline.py mixed_content/ processed/
```

## 🔄 Comparison with Previous Weeks

### Week0506_Mkhoi_OCR_ASR
- ✅ Copied: Audio extraction, Whisper transcription
- ✨ Enhanced: Chunked processing, frame extraction, multiple output formats

### Week0506_QPhu_Processor
- ✅ Copied: Docling document processing
- ✨ Enhanced: Integrated into 3-stage pipeline, handles normalized inputs

### Week070809 (This Week)
- ✨ **NEW**: Complete normalization layer
- ✨ **NEW**: Unified pipeline orchestration
- ✨ **NEW**: Support for ALL document types
- ✨ **NEW**: Optimized for RAG pipelines

---

**Happy Processing! 🎉**
