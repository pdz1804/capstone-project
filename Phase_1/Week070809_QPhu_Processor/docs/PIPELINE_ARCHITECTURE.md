# Document Processing Pipeline - Architecture Overview

## Table of Contents
1. [Overview](#overview)
2. [Three-Stage Architecture](#three-stage-architecture)
3. [Data Flow](#data-flow)
4. [Design Rationale](#design-rationale)
5. [Key Components](#key-components)
6. [Configuration System](#configuration-system)

---

## Overview

The Document Processing Pipeline is a comprehensive, production-ready system that transforms any document type into RAG-ready formats. It implements a **three-stage architecture** optimized for **dual-mode RAG** (text-based + image-based retrieval).

### Purpose
Prepare diverse document formats (DOCX, PPTX, PDF, HTML, Images, Excel, CSV, Video, Audio) for Retrieval-Augmented Generation (RAG) systems.

### Target Use Cases
- **Educational Content Processing**: Lecture slides, videos, papers
- **Enterprise Document Processing**: Reports, presentations, spreadsheets
- **Multimodal RAG Systems**: Text + image retrieval pipelines
- **Knowledge Base Construction**: Converting legacy documents to searchable format

---

## Three-Stage Architecture

### Pipeline Visualization

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RAW INPUT FILES                              │
│  📄 DOCX, PPTX, HTML, Images, Excel, CSV, Video, Audio, PDF, MD    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STAGE 1: NORMALIZATION                             │
│                    (normalizer.py)                                   │
│                                                                      │
│  Purpose: Convert diverse formats to standardized PDF/Markdown      │
│  ─────────────────────────────────────────────────────────────────  │
│  • DOCX/PPTX/HTML → PDF (preserves visual layout)                  │
│  • Standalone Images → PDF (for image-based RAG)                    │
│  • Excel/CSV → Markdown tables (text-only)                          │
│  • Keep original files for Stage 3 processing                       │
│                                                                      │
│  Why: Create PDFs for image-based RAG while preserving originals   │
│       for high-quality Docling processing                           │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STAGE 2: MEDIA PROCESSING                          │
│                   (media_processor.py)                               │
│                                                                      │
│  Purpose: Extract text and frames from video/audio files            │
│  ─────────────────────────────────────────────────────────────────  │
│  • Video → Audio Extraction (MoviePy)                               │
│  • Audio → Text Transcription (Whisper ASR)                         │
│  • Video → Frame Extraction (OpenCV, optional)                      │
│  • Generate: TXT, JSON, SRT, VTT formats                            │
│                                                                      │
│  Why: Convert multimedia to text for downstream processing          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                STAGE 3: DOCUMENT PROCESSING                          │
│                  (document_processor.py)                             │
│                                                                      │
│  Purpose: Deep document analysis using Docling                      │
│  ─────────────────────────────────────────────────────────────────  │
│  • Process ORIGINAL files (DOCX, PPTX, HTML, Images)               │
│  • Advanced OCR (RapidOCR, Tesseract, EasyOCR)                     │
│  • Visual Language Model (VLM) for image understanding              │
│  • Table extraction and structure preservation                      │
│  • Export: Markdown, images, tables, metadata (JSON)               │
│                                                                      │
│  Why: Use originals (not Stage 1 PDFs) for best extraction quality │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FINAL RAG-READY OUTPUTS                         │
│                                                                      │
│  📄 Text-based RAG: Docling-processed Markdown files                │
│  🖼️  Image-based RAG: Normalized PDFs + extracted images           │
│  📊 Structured Data: JSON metadata, CSV tables                      │
│  📈 Analytics: Processing statistics and logs                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Input → Processing → Output Flow

| **Input Type** | **Stage 1: Normalization** | **Stage 2: Media** | **Stage 3: Docling** | **Final Output** |
|----------------|---------------------------|-------------------|---------------------|------------------|
| **DOCX** | → PDF (LibreOffice)<br>→ Keep original |   | Original → Markdown<br>Extract: images, tables | • PDF (image RAG)<br>• MD (text RAG)<br>• Images, tables |
| **PPTX** | → PDF (LibreOffice)<br>→ Keep original |   | Original → Markdown<br>Extract: images, text | • PDF (image RAG)<br>• MD (text RAG)<br>• Slide images |
| **HTML** | → PDF (Markdown)<br>→ Keep original |   | Original → Markdown | • PDF (image RAG)<br>• MD (text RAG) |
| **Images** | → PDF (img2pdf)<br>→ Keep original |   | Original → Markdown<br>OCR + VLM | • PDF (image RAG)<br>• MD with OCR text<br>• Image descriptions |
| **Excel/CSV** | → Markdown tables<br>❌ No original kept |   | ❌ Not processed | • MD (tables only) |
| **Video (MP4)** |   | → Audio → Text<br>→ Frames (optional) | Transcript → Markdown | • MD (text RAG)<br>• Frame images<br>• SRT/VTT subtitles |
| **Audio (WAV)** |   | → Text (Whisper) | Transcript → Markdown | • MD (text RAG)<br>• Transcript formats |
| **PDF** | ✅ Copy as-is<br>→ Keep original |   | Original → Markdown<br>OCR + layout | • PDF (as-is)<br>• MD (text RAG)<br>• Extracted content |
| **Markdown** | ✅ Copy as-is<br>→ Keep original |   | Original → Markdown<br>Re-process | • MD (normalized) |

### Key Design Decisions

1. **Why create PDFs if we process originals?**
   - PDFs are for **image-based RAG** (visual similarity search)
   - Originals are for **text extraction** (better quality than PDF re-processing)

2. **Why keep original files?**
   - Docling works best on original DOCX/PPTX (preserves formatting)
   - Converting DOCX → PDF → Markdown loses information
   - Solution: Create PDFs for image RAG, process originals for text RAG

3. **Why separate media processing?**
   - Video/audio require specialized tools (Whisper, MoviePy)
   - Transcripts become text files that flow to Stage 3
   - Enables GPU acceleration for ASR independently

---

## Design Rationale

### Problem: Diverse Document Formats
Organizations have documents in 10+ formats (DOCX, PDF, HTML, videos, etc.). Traditional RAG systems only handle PDFs or plain text.

### Solution: Three-Stage Normalization Pipeline
1. **Convert everything to standard formats** (PDF + Markdown)
2. **Extract multimedia content** (transcribe videos/audio)
3. **Deep analysis with Docling** (OCR, VLM, structure extraction)

### Why Three Stages?

#### Stage 1: Normalization
- **Problem**: RAG systems need consistent formats
- **Solution**: Convert diverse formats → PDF (for images) + Markdown (for text)
- **Technology**: LibreOffice (DOCX/PPTX), BeautifulSoup (HTML), Pandas (Excel)

#### Stage 2: Media Processing
- **Problem**: Videos and audio contain valuable information but aren't text-searchable
- **Solution**: Transcribe with state-of-the-art ASR (Whisper)
- **Technology**: Whisper (OpenAI), MoviePy (video handling), OpenCV (frames)

#### Stage 3: Document Processing
- **Problem**: Need deep document understanding (layout, images, tables)
- **Solution**: Use Docling's multimodal processing (OCR + VLM + structure)
- **Technology**: Docling (IBM Research), RapidOCR, Vision-Language Models

---

## Key Components

### 1. Pipeline Orchestrator (`pipeline.py`)
**Purpose**: Coordinates all three stages and manages configuration

**Key Functions**:
- `DocumentProcessingPipeline.__init__()`: Initialize pipeline with configuration
- `run()`: Execute all three stages sequentially
- `_run_normalization()`: Stage 1 execution
- `_run_media_processing()`: Stage 2 execution
- `_run_document_processing()`: Stage 3 execution
- `_save_pipeline_stats()`: Generate processing report

**Configuration**: `PipelineConfig` dataclass
- Controls which stages to run
- Sub-configurations for each stage
- GPU/performance settings

### 2. Document Normalizer (`normalizer.py`)
**Purpose**: Convert diverse formats to PDF and Markdown

**Key Classes**:
- `NormalizerConfig`: Configuration for normalization behavior
- `DocumentNormalizer`: Main normalization engine

**Conversion Methods**:
- `_normalize_docx()`: DOCX → PDF (LibreOffice) + Markdown
- `_normalize_pptx()`: PPTX → PDF (LibreOffice) + Markdown
- `_normalize_html()`: HTML → Markdown (BeautifulSoup)
- `_normalize_excel()`: XLSX → Markdown tables (Pandas)
- `_normalize_csv()`: CSV → Markdown tables
- `_normalize_image()`: Image → PDF (img2pdf)

**Special Feature**: LibreOffice Integration
- Highest quality DOCX/PPTX → PDF conversion
- Preserves images, layout, formatting
- Fallback to ReportLab if LibreOffice not available

### 3. Media Processor (`media_processor.py`)
**Purpose**: Process video and audio files

**Key Classes**:
- `MediaProcessorConfig`: Configuration for media processing
- `AudioExtractor`: Extract audio from video
- `AudioTranscriber`: Transcribe audio with Whisper
- `FrameExtractor`: Extract video frames
- `MediaProcessor`: Orchestrates all media operations

**Processing Flow**:
```
Video (MP4) → AudioExtractor → Audio (WAV)
                                   ↓
                            AudioTranscriber (Whisper)
                                   ↓
                            Transcript (TXT, JSON, SRT, VTT)
```

**Transcription Features**:
- Multiple Whisper models (tiny, base, small, medium, large)
- GPU acceleration support
- Chunked processing for long audio (avoids memory issues)
- Multiple output formats (plain text, JSON with timestamps, SRT/VTT subtitles)

### 4. Document Processor (`document_processor.py`)
**Purpose**: Deep document analysis with Docling

**Key Classes**:
- `ProcessingConfig`: Configuration for Docling processing
- `MultimodalDocumentProcessor`: Main Docling orchestrator

**Advanced Features**:
1. **OCR Engines** (RapidOCR, Tesseract, EasyOCR)
   - Extracts text from scanned PDFs and images
   - Language-specific processing
   
2. **Visual Language Model (VLM)**
   - Generates image descriptions
   - Understands diagrams, charts, figures
   
3. **Table Extraction**
   - Preserves table structure
   - Exports to CSV + Markdown
   
4. **Layout Analysis**
   - Detects sections, headings, lists
   - Maintains document hierarchy
   
5. **Image Filtering**
   - Filters out small icons (<100x100px)
   - Keeps only meaningful images
   - Quality-based selection

**Processing Methods**:
- `process_batch()`: Process entire directory
- `_process_single_file()`: Process one file
- `_export_markdown()`: Generate Markdown output
- `_export_images()`: Save extracted images (with filtering)
- `_export_tables()`: Save tables (CSV + MD)
- `_export_metadata()`: Save processing metadata (JSON)

---

## Configuration System

### Hierarchical Configuration

```python
PipelineConfig
├── enable_normalization: bool
├── enable_media_processing: bool  
├── enable_document_processing: bool
├── normalizer_config: NormalizerConfig
│   ├── generate_pdf: bool
│   ├── generate_markdown: bool
│   ├── image_quality: int
│   └── ...
├── media_config: MediaProcessorConfig
│   ├── extract_audio: bool
│   ├── enable_transcription: bool
│   ├── asr_model: str (tiny/base/small/medium/large)
│   └── ...
└── document_config: ProcessingConfig
    ├── use_gpu: bool
    ├── enable_ocr: bool
    ├── enable_vlm: bool
    ├── ocr_engine: str (rapidocr/tesseract/easyocr)
    └── ...
```

### Default Configuration
All stages enabled with production-ready defaults:
- **Normalization**: Both PDF and Markdown generation
- **Media**: Whisper 'base' model (good speed/accuracy balance)
- **Document**: GPU-accelerated Docling with OCR + VLM

### Customization Examples

**Minimal Configuration** (fastest):
```python
config = PipelineConfig(
    normalizer_config=NormalizerConfig(generate_pdf=False),
    media_config=MediaProcessorConfig(asr_model="tiny"),
    document_config=ProcessingConfig(enable_vlm=False)
)
```

**Maximum Quality** (slowest):
```python
config = PipelineConfig(
    normalizer_config=NormalizerConfig(image_quality=100),
    media_config=MediaProcessorConfig(asr_model="large-v3"),
    document_config=ProcessingConfig(enable_vlm=True, enable_ocr=True)
)
```

**Text-Only RAG**:
```python
config = PipelineConfig(
    normalizer_config=NormalizerConfig(generate_pdf=False),
    media_config=MediaProcessorConfig(extract_frames=False),
    document_config=ProcessingConfig(export_images=False)
)
```

---

## Output Structure

### Directory Layout
```
output/
├── pipeline_stats.json                    # Overall statistics
├── stage1_normalized/                     # Normalization outputs
│   ├── normalized_pdfs/                  # PDFs for image-based RAG
│   ├── normalized_markdown/               # Markdown for text-based RAG
│   ├── original_files/                    # Copies of originals for Stage 3
│   └── normalization_metadata/
│       └── normalization_stats.json
├── stage2_media_processed/                # Media processing outputs
│   ├── extracted_audio/                   # WAV audio files
│   ├── transcripts/                       # TXT, JSON, SRT, VTT
│   ├── extracted_frames/                  # Video frames (if enabled)
│   └── media_metadata/
│       └── media_processing_stats.json
└── stage3_document_processed/             # Docling outputs
    ├── document1/                         # Per-document folders
    │   ├── document1.md                  # Final markdown
    │   ├── document1_metadata.json       # Processing metadata
    │   ├── images/                        # Extracted images (filtered)
    │   └── tables/                        # Extracted tables
    └── logs/
        └── batch_summary_*.json
```

### Metadata Files

**Pipeline Stats** (`pipeline_stats.json`):
```json
{
  "start_time": "2025-11-21T10:30:00",
  "end_time": "2025-11-21T10:35:00",
  "total_input_files": 25,
  "total_output_files": 75,
  "stages": {
    "normalization": {...},
    "media_processing": {...},
    "document_processing": {...}
  }
}
```

**Document Metadata** (`*_metadata.json`):
```json
{
  "source_file": "lecture.pptx",
  "processing_date": "2025-11-21T10:32:00",
  "docling_version": "1.x",
  "processing_time": 12.5,
  "statistics": {
    "pages": 25,
    "images_found": 15,
    "images_exported": 10,
    "tables": 3,
    "total_text_length": 5000
  }
}
```

---

## Performance Characteristics

### Processing Speed (Approximate)

| **File Type** | **Size** | **Stage 1** | **Stage 2** | **Stage 3** | **Total** |
|--------------|---------|------------|------------|------------|-----------|
| DOCX (10 pages) | 500KB | 5s |   | 15s | **20s** |
| PPTX (20 slides) | 5MB | 10s |   | 30s | **40s** |
| PDF (50 pages) | 10MB | 1s |   | 60s | **61s** |
| Image (high-res) | 5MB | 2s |   | 10s | **12s** |
| Video (10 min) | 100MB |   | 120s | 5s | **125s** |

**Note**: Times vary based on:
- Document complexity
- Hardware (GPU vs CPU)
- Model sizes (Whisper tiny vs large)
- Content (text-heavy vs image-heavy)

### Resource Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 8GB
- Storage: 2x input size

**Recommended**:
- CPU: 8+ cores
- RAM: 16GB
- GPU: 6GB VRAM (for Whisper large + VLM)
- Storage: 3x input size

---

## Error Handling

### Graceful Degradation
- If LibreOffice unavailable → Fallback to ReportLab
- If GPU unavailable → Use CPU for processing
- If Whisper model too large → Use smaller model
- If file processing fails → Continue with other files

### Logging Strategy
- **Console**: Progress bars and high-level status
- **File logs**: Detailed per-stage logs
- **Metadata**: Processing statistics and errors

---

## Next Steps

For detailed function documentation, see:
- [STAGE1_NORMALIZATION.md](STAGE1_NORMALIZATION.md) - Document normalization details
- [STAGE2_MEDIA.md](STAGE2_MEDIA.md) - Media processing details  
- [STAGE3_DOCUMENT.md](STAGE3_DOCUMENT.md) - Docling processing details
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API documentation
