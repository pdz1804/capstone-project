# AI Service Pipelines   Comprehensive & Accurate Documentation

**Version:** 3.0 (Verified with Actual Code)  
**Date:** May 2026  
**Scope:** Phase 2 AI Service   7-stage processing + indexing + search pipelines

---

## Executive Summary

The Phase 2 AI Service implements a **sophisticated 7-stage pipeline** that intelligently routes different file types through specialized processors:

- **Stage 1:** Normalization (format detection & conversion)
- **Stage 2:** Media Processing (audio/video extraction & transcription)
- **Stage 3:** Docling Document Processing (general-purpose document parsing)
- **Stage 3b:** Excel Processing (custom XML parser + table-aware chunking)
- **Stage 3c:** DOCX Processing (custom XML parser + heading-aware chunking)  
- **Stage 3d:** PDF Processing (born-digital custom parser + heading-aware chunking)
- **Stage 4:** RAG-Ready Consolidation

Each stage 3 variant (3b, 3c, 3d) **runs conditionally** based on whether its input type is detected in Stage 1 outputs.

---

## Table of Contents

1. [Pipeline Architecture Overview](#pipeline-architecture-overview)
2. [7-Stage Pipeline Model](#7-stage-pipeline-model)
3. [Stage 1: Normalization](#stage-1-normalization)
4. [Stage 2: Media Processing](#stage-2-media-processing)
5. [Stage 3: Main Document Processing (Docling)](#stage-3-main-document-processing-docling)
6. [Stage 3b: Excel Processing (Conditional)](#stage-3b-excel-processing-conditional)
7. [Stage 3c: DOCX Processing (Conditional)](#stage-3c-docx-processing-conditional)
8. [Stage 3d: PDF Processing (Conditional)](#stage-3d-pdf-processing-conditional)
9. [Stage 4: RAG-Ready Consolidation](#stage-4-rag-ready-consolidation)
10. [Indexing Pipeline](#indexing-pipeline)
11. [Search & Retrieval Pipeline](#search--retrieval-pipeline)
12. [Storage Architecture](#storage-architecture)

---

## Pipeline Architecture Overview

This document covers the **Processing, Indexing, and Search/Retrieval pipelines** of the Phase 2 AI Service. It does not cover the overall system architecture (API server, UI, storage layer, etc.), only the pipeline flows.

```mermaid
graph TB
    A["📁 User Upload"] --> B["🔄 Storage Layer<br/>Local or S3"]
    B --> C["7-Stage<br/>Processing Pipeline"]
    C -->|stage4_rag_ready| D["📑 RAG-Ready<br/>Documents"]
    D -->|Index| E["🔍 Indexing Pipeline"]
    E -->|Text: Dense + BM25<br/>Image: ColQwen| F["🗂️ Qdrant + BM25"]
    F --> G["🎯 Search Pipeline"]
    G -->|Optional| H["💡 LLM Generation"]
    H -->|Results| I["👤 User Response"]
    
    style A fill:#e1f5ff
    style C fill:#fff3e0
    style D fill:#c8e6c9
    style E fill:#fff9c4
    style G fill:#ffccbc
    style I fill:#b2dfdb
```

---

## 7-Stage Pipeline Model

### Complete Pipeline Architecture

```mermaid
graph LR
    A["📤 Input"] --> S1["Stage 1<br/>Normalization"]
    
    S1 -->|PDFs| S1_OUT["normalized_pdfs/"]
    S1 -->|Markdown| S1_OUT2["normalized_markdown/"]
    S1 -->|Excel JSON| S1_OUT3["excel_parsed/"]
    S1 -->|DOCX JSON| S1_OUT4["docx_parsed/"]
    S1 -->|PDF JSON| S1_OUT5["pdf_parsed/"]
    S1 -->|Video/Audio| S2["Stage 2<br/>Media Processing"]
    
    S1_OUT --> S3["Stage 3<br/>Docling"]
    S1_OUT2 --> S3
    S1_OUT3 --> S3B["Stage 3b<br/>Excel"]
    S1_OUT4 --> S3C["Stage 3c<br/>DOCX"]
    S1_OUT5 --> S3D["Stage 3d<br/>PDF"]
    
    S2 -->|Transcripts<br/>Frames| S3
    S2 -->|Media Data| S4["Stage 4<br/>Consolidation"]
    
    S3 -->|Docling Output| S4
    S3B -->|Direct| S4
    S3C -->|Direct| S4
    S3D -->|Direct| S4
    
    S4 -->|stage4_rag_ready| F["🔍 Indexing"]
    
    style S1 fill:#fff3e0
    style S2 fill:#fce4ec
    style S3 fill:#f3e5f5
    style S3B fill:#e1bee7
    style S3C fill:#e1bee7
    style S3D fill:#e1bee7
    style S4 fill:#c8e6c9
    style F fill:#fff9c4
```

### Stage Summary Table

| Stage | Name | Processor | Input | Output | Condition |
|-------|------|-----------|-------|--------|-----------|
| **1** | Normalization | DocumentNormalizer | Raw files | Normalized PDFs/JSON/Markdown | Always runs |
| **2** | Media Processing | MediaProcessor | MP4, WAV, MP3, etc. | Transcripts, Frames, Audio | If media files present |
| **3** | Document Processing (Docling) | DocumentConverter | Normalized PDFs, Markdown | Markdown with extracted tables and images | Always runs |
| **3b** | Excel Processing | ExcelPreprocessor | excel_parsed/ JSON | RAG-ready chunks | If `excel_parsed/` exists |
| **3c** | DOCX Processing | DocxPreprocessor | docx_parsed/ JSON | RAG-ready chunks | If `docx_parsed/` exists |
| **3d** | PDF Processing | PdfPreprocessor | pdf_parsed/ JSON | RAG-ready chunks | If `pdf_parsed/` exists |
| **4** | Consolidation | Stage4Consolidator | All stage 3 outputs + media | stage4_rag_ready/ | Always runs |

---

## Stage 1: Normalization

### Purpose
Detects input file types and routes them appropriately:
- **Custom parsers**: XML-based parsing for Excel/DOCX/PDF → JSON
- **Format conversion**: DOCX/PPTX → PDF, TXT → Markdown
- **Passthrough**: CSV, AsciiDoc, VTT, Images → just copy, let Docling handle natively

### File Type Routing

```mermaid
graph TD
    A["Input File"] --> B{File Type}
    
    B -->|DOCX/DOC| B1["Custom XML<br/>Parser"]
    B1 -->|Output| B1_OUT["docx_parsed/<br/>JSON"]
    B1_OUT -->|Stage 3c| B1_NEXT["DocxPreprocessor"]
    
    B -->|XLSX/XLSM/XLS| B2["Custom XML<br/>Parser"]
    B2 -->|Output| B2_OUT["excel_parsed/<br/>JSON"]
    B2_OUT -->|Stage 3b| B2_NEXT["ExcelPreprocessor"]
    
    B -->|PDF| B3["Classify & Parse<br/>Born-digital check"]
    B3 -->|If born-digital| B3A["PDF Parser"]
    B3A -->|Output| B3A_OUT["pdf_parsed/<br/>JSON"]
    B3A_OUT -->|Stage 3d| B3_NEXT["PdfPreprocessor"]
    B3 -->|Always| B3B["Copy to<br/>normalized_pdfs/"]
    B3B -->|Output| B3B_OUT["normalized_pdfs/<br/>PDF"]
    
    B -->|PPTX/PPT| C["Convert to PDF<br/>LibreOffice"]
    C -->|Output| C_PDF["normalized_pdfs/"]
    
    B -->|HTML/HTM| D["Extract & Convert<br/>BeautifulSoup"]
    D -->|Output| D_MD["normalized_markdown/"]
    
    B -->|TXT| E["Convert<br/>TXT → Markdown"]
    E -->|Output| E_MD["normalized_markdown/"]
    
    B -->|Markdown| F["Copy to<br/>normalized_markdown/"]
    
    B -->|CSV/AsciiDoc/VTT| G["Copy ONLY<br/>No conversion"]
    G -->|Destination| G_OUT["original_files/"]
    
    B -->|Images<br/>PNG/JPG/GIF/TIFF| J["Copy ONLY<br/>No conversion"]
    J -->|Destination| J_OUT["original_files/"]
    
    B -->|Video/Audio| K["→ Stage 2<br/>Media Processing"]
    
    B1_OUT -.->|Also copy| P["original_files/"]
    B2_OUT -.->|Also copy| P
    B3A_OUT -.->|Also copy| P
    
    B3B_OUT -->|Stage 3| T["Docling<br/>processing"]
    C_PDF -->|Stage 3| T
    D_MD -->|Stage 3| T
    E_MD -->|Stage 3| T
    F -->|Stage 3| T
    G_OUT -->|Stage 3| T
    J_OUT -->|Stage 3| T
    
    B1_NEXT --> CONSOL["→ Consolidate to<br/>stage4_rag_ready/"]
    B2_NEXT --> CONSOL
    B3_NEXT --> CONSOL
    T --> CONSOL
    K -->|Transcripts| T
    
    style B1 fill:#e1bee7
    style B2 fill:#e1bee7
    style B3 fill:#e1bee7
    style B3A fill:#e1bee7
    style G fill:#ffccbc
    style J fill:#ffccbc
    style T fill:#c8e6c9
    style CONSOL fill:#a5d6a7
```

### Stage 1 Processing Details

| File Type | Handler | Output Location | Process | Destination for Stage 3 |
|-----------|---------|-----------------|---------|-------------------------|
| **DOCX/DOC** | Custom XML Parser | `docx_parsed/` (JSON) | Parses heading hierarchy + content | → Stage 3c (DocxPreprocessor) |
| **XLSX/XLSM/XLS** | Custom XML Parser | `excel_parsed/` (JSON) | Parses table structures + data | → Stage 3b (ExcelPreprocessor) |
| **PDF** | Born-digital Parser | `pdf_parsed/` (JSON) | Extracts heading hierarchy + content | → Stage 3d (PdfPreprocessor) |
| **PPTX/PPT** | LibreOffice | `normalized_pdfs/` (PDF) | Converts to PDF | → Stage 3 (Docling) |
| **HTML/HTM** | BeautifulSoup | `normalized_markdown/` (MD) | Extracts text & structure | → Stage 3 (Docling) |
| **TXT** | Simple converter | `normalized_markdown/` (MD) | Converts to markdown | → Stage 3 (Docling) |
| **MD** | Direct copy | `normalized_markdown/` (MD) | No conversion needed | → Stage 3 (Docling) |
| **CSV** | ⚠️ **Copy ONLY** | `original_files/` | **NOT normalized**, copied as-is | → Stage 3 (Docling processes natively) |
| **AsciiDoc** (.adoc, .asciidoc, .asc) | ⚠️ **Copy ONLY** | `original_files/` | **NOT normalized**, copied as-is | → Stage 3 (Docling processes natively) |
| **VTT** (Subtitles) | ⚠️ **Copy ONLY** | `original_files/` | **NOT normalized**, copied as-is | → Stage 3 (Docling processes natively) |
| **Images** (PNG, JPG, TIFF, etc.) | ⚠️ **Copy ONLY** | `original_files/` | **NOT converted to PDF**, copied as-is | → Stage 3 (Docling processes natively with VLM/OCR) |
| **Video/Audio** (MP4, WAV, MP3, etc.) | Media detection | *Skipped* | Not copied to originals | → Stage 2 (Media Processing) |

### Stage 1 Output Directory Structure

```
output/stage1_normalized/
│
├── normalized_pdfs/              # Converted PDFs
│   ├── presentation.pdf          # From PPTX (LibreOffice)
│   └── document.pdf              # From direct copy
│
├── normalized_markdown/          # Converted Markdown
│   ├── webpage.md                # From HTML (BeautifulSoup)
│   ├── notes.md                  # From TXT
│   └── readme.md                 # From direct copy
│
├── docx_parsed/                  # ✓ CUSTOM PARSER OUTPUT (JSON)
│   ├── word_doc1.json            # Heading tree + content structure
│   └── word_doc2.json
│
├── excel_parsed/                 # ✓ CUSTOM PARSER OUTPUT (JSON)
│   ├── spreadsheet1.json         # Table structures + data
│   └── spreadsheet2.json
│
├── pdf_parsed/                   # ✓ CUSTOM PARSER OUTPUT (JSON)
│   ├── born_digital1.json        # Heading hierarchy + layout
│   └── born_digital2.json
│
└── original_files/               # ⚠️ PASSTHROUGH (Not normalized)
    ├── data.csv                  # CSV copied as-is
    ├── docs.adoc                 # AsciiDoc copied as-is
    ├── movie.vtt                 # VTT copied as-is
    ├── diagram.png               # Image copied as-is (NOT to PDF!)
    ├── photo.jpg                 # Image copied as-is
    ├── word_doc1.docx            # Backup of DOCX original
    ├── spreadsheet1.xlsx         # Backup of Excel original
    └── ...
```

### Key Insights about Stage 1

✅ **CSV, AsciiDoc, VTT, Images**: 
- **NOT normalized or converted**
- Just copied to `original_files/`
- Docling in Stage 3 handles them natively
- Images specifically: "Do NOT convert to PDF! Docling processes images better natively"

✅ **Excel, DOCX, PDF**:
- **Custom XML parsers** extract structure to JSON
- JSON consumed by Stage 3b/3c/3d processors
- Original files also copied to `original_files/` as backup

✅ **PPTX, HTML, TXT**:
- **Format conversion** to PDF or Markdown
- Ready for Stage 3 Docling processing

---

## Stage 2: Media Processing

### Purpose
Extract, transcribe, and process media files (videos and audio) to produce searchable text and visual content.

### Supported Media Types

**Video Formats:** `.mp4` | `.avi` | `.mov` | `.mkv` | `.flv` | `.wmv` | `.webm`

**Audio Formats:** `.wav` | `.mp3` | `.m4a` | `.flac` | `.ogg` | `.aac`

### Media Processing Flow

```mermaid
graph TD
    A["Input Media File"] --> B{File Type?}
    
    B -->|Video| C["VIDEO PATH<br/>MP4, AVI, MOV, MKV"]
    B -->|Audio| D["AUDIO PATH<br/>WAV, MP3, M4A"]
    
    C -->|Extract Audio<br/>MoviePy| E["WAV Audio"]
    C -->|Extract Frames<br/>OpenCV| F["Frame Images"]
    
    D --> E
    
    E -->|Noise Reduction<br/>High-pass filter 80Hz| G["Cleaned Audio"]
    G -->|Transcribe<br/>Whisper Model| H["Transcript<br/>segments + timestamps"]
    
    H -->|Chunk<br/>100 tokens per chunk| I["Transcript Chunks<br/>with metadata"]
    
    F -->|Check Quality<br/>Laplacian variance| J["Quality Frames"]
    J -->|Deduplicate<br/>Perceptual hashing| K["Unique Frames<br/>similarity threshold 0.95"]
    
    I -->|Associate by<br/>timestamp| L["Frame-Chunk Binding"]
    K -->|Associate by<br/>timestamp| L
    
    L -->|Output| M["Uniform Metadata<br/>bidirectional linking"]
    
    style C fill:#fce4ec
    style D fill:#fce4ec
    style E fill:#fff9c4
    style G fill:#c8e6c9
    style H fill:#c8e6c9
    style K fill:#b2dfdb
    style M fill:#a5d6a7
```

### Stage 2 Output Directory Structure

```
output/stage2_media_processed/
├── extracted_audio/
│   ├── video1.wav                 # Extracted audio (16 kHz, mono)
│   └── audio_file.wav
│
├── transcripts/                   # Full Whisper output (5 formats)
│   ├── video1.json                # Full metadata with segments
│   ├── video1.txt                 # Plain text
│   ├── video1.md                  # Markdown with [HH:MM:SS] timestamps
│   ├── video1.srt                 # SRT subtitle format
│   ├── video1.vtt                 # WebVTT subtitle format
│   └── ...
│
├── transcript_chunks/
│   ├── video1_chunks.json         # {metadata, chunks[]}
│   │                              # Each chunk: text, token_count, start_time, 
│   │                              #              end_time, associated_frames
│   └── ...
│
├── extracted_frames/
│   ├── video1/
│   │   ├── frame_000000.jpg       # Frame at t=0s
│   │   ├── frame_000030.jpg       # Every Nth frame
│   │   ├── frame_000060.jpg
│   │   └── ...
│   └── video2/
│       └── ...
│
└── media_metadata/
    ├── video1_metadata.json            # Provenance + processing info
    ├── video1_frame_metadata.json      # Frame hashes, dedup info
    │                                   # {frame_path, frame_index, 
    │                                   #  is_duplicate, associated_chunk_index}
    ├── audio_file_metadata.json
    └── processing_statistics.json      # Summary stats
```

---

## Stage 3: Main Document Processing (DocumentProcessorV2 Unified Router)

### Purpose & Overall Flow

Stage 3 is the **intelligent document processing hub** that handles multiple file types through parallel processing paths. Here's how it works:

**Stage 3 consists of 4 parallel paths:**

1. **Stage 3 (Main)**: DocumentProcessorV2 Unified Router   processes normalized PDFs, markdown, and original files (CSV, AsciiDoc, VTT, Images) that are **not handled by Stage 3b/3c/3d custom parsers**

2. **Stage 3b (Excel)**: ExcelPreprocessor   runs **only if** Excel files were detected and parsed in Stage 1 (JSON in `excel_parsed/`)

3. **Stage 3c (DOCX)**: DocxPreprocessor   runs **only if** Word documents were detected and parsed in Stage 1 (JSON in `docx_parsed/`)

4. **Stage 3d (PDF)**: PdfPreprocessor   runs **only if** PDF files were detected and parsed in Stage 1 (JSON in `pdf_parsed/`)

**Key Design**: Stages 3b/3c/3d run **conditionally**   they only execute if their specialized input exists. Meanwhile, Stage 3 (V2 Router) handles all other file types. Both output directly to `stage4_rag_ready/`, which Stage 4 then consolidates.

**Processing Timeline**:
- Stage 3 (V2 Router) runs first, handling normalized PDFs, Markdown, and passthrough files
- Stages 3b, 3c, and 3d run **sequentially after** Stage 3 (conditional   only if their parsed inputs exist from Stage 1)
  - Stage 3b: ExcelPreprocessor (if `excel_parsed/` exists)
  - Stage 3c: DocxPreprocessor (if `docx_parsed/` exists)
  - Stage 3d: PdfPreprocessor (if `pdf_parsed/` exists)
- Each sub-stage outputs directly to its own document folder in `stage4_rag_ready/`
- Stage 4 (Consolidation) runs last and merges all outputs into a unified RAG-ready structure
- **Note**: Parallel execution is currently disabled (`parallel_processing: false`); this is planned as a future enhancement.

### Supported Input Formats (10 Types via DocumentProcessorV2)

Docling DocumentConverter supports these 10 format families:

```mermaid
graph TD
    A["All Input Types"] --> B{File Type}
    
    B -->|PDF| B1["📄 PDF<br/>.pdf"]
    B -->|Word| B2["📝 DOCX/DOC<br/>.docx, .doc"]
    B -->|PowerPoint| B3["🎯 PPTX/PPT<br/>.pptx, .ppt"]
    B -->|Excel| B4["📊 XLSX/XLS<br/>.xlsx, .xls"]
    B -->|Web| B5["🌐 HTML<br/>.html, .htm, .xhtml"]
    B -->|Text| B6["📋 Markdown<br/>.md"]
    B -->|Data| B7["📈 CSV<br/>.csv"]
    B -->|Images| B8["🖼️ Images<br/>.png, .jpg, .jpeg,<br/>.tiff, .tif, .bmp, .webp"]
    B -->|Documentation| B9["📖 AsciiDoc<br/>.adoc, .asciidoc, .asc"]
    B -->|Subtitles| B10["🎬 WebVTT<br/>.vtt"]
    
    style A fill:#f3e5f5
    style B1 fill:#e1bee7
    style B2 fill:#e1bee7
    style B3 fill:#e1bee7
    style B4 fill:#e1bee7
    style B5 fill:#e1bee7
    style B6 fill:#e1bee7
    style B7 fill:#e1bee7
    style B8 fill:#e1bee7
    style B9 fill:#e1bee7
    style B10 fill:#e1bee7
```

**Complete Format List:**
- **PDF** → `.pdf`
- **Microsoft Word** → `.docx`, `.doc`
- **PowerPoint** → `.pptx`, `.ppt`
- **Excel Spreadsheets** → `.xlsx`, `.xls`
- **Web Pages** → `.html`, `.htm`, `.xhtml`
- **Markdown** → `.md`
- **Comma-Separated Data** → `.csv`
- **Images with OCR** → `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`
- **AsciiDoc** → `.adoc`, `.asciidoc`, `.asc` (technical documentation format)
- **WebVTT Subtitles** → `.vtt` (video subtitle format)

### Stage 3 Smart Deduplication Logic

```mermaid
graph TD
    A["Input Files"] --> B["Check Normalized<br/>Outputs"]
    
    B -->|1. Normalized PDFs| B1["Process via Docling<br/>(unless from DOCX/PDF custom parser)"]
    B -->|2. Normalized Markdown| B2["Process via Docling"]
    
    B1 -->|Skip if| B1_SKIP["✗ In docx_parsed/"]
    B1 -->|Skip if| B1_SKIP2["✗ In pdf_parsed/"]
    B1_SKIP -->|Custom parser handles| B1_SKIP_OUT["→ Stage 3c<br/>→ Stage 3d"]
    B1_SKIP2 -->|Custom parser handles| B1_SKIP_OUT
    
    B -->|3. Original Files| B3["Check if converted<br/>to PDF or MD"]
    
    B3 -->|Already converted| B3_SKIP["✗ Skip<br/>(already processed)"]
    B3 -->|Not converted| B3_KEEP["✓ Keep"]
    
    B3_KEEP -->|Check type| B3_TYPE{Type?}
    
    B3_TYPE -->|XLSX/XLS in excel_parsed/| B3_SKIP2["✗ Skip<br/>Stage 3b handles"]
    B3_TYPE -->|DOCX/DOC in docx_parsed/| B3_SKIP3["✗ Skip<br/>Stage 3c handles"]
    B3_TYPE -->|PDF in pdf_parsed/| B3_SKIP4["✗ Skip<br/>Stage 3d handles"]
    B3_TYPE -->|Other Docling types| B3_PROC["✓ Process"]
    
    B3_PROC -->|Can be| B3_PROC_EX["PNG/JPG/TIFF (OCR)<br/>CSV (parse)<br/>AsciiDoc (parse)<br/>HTML (extract)<br/>VTT (parse)<br/>etc."]
    
    B1 -->|Final| C["→ Docling<br/>DocumentConverter"]
    B2 -->|Final| C
    B3_PROC -->|Final| C
    
    C -->|Extract| D["Text + Tables<br/>+ Images"]
    D -->|Output| E["stage3_document_processed/"]
    
    style A fill:#f3e5f5
    style C fill:#b39ddb
    style E fill:#c8e6c9
```

### DocumentProcessorV2 Unified Router (Current Implementation)

**Architecture**: Intelligent file-type router with specialized processors for each format

```mermaid
graph TD
    A["Stage 3: DocumentProcessorV2<br/>Unified Router"] --> B["Intelligent Router<br/>analyzes file type"]
    
    B -->|Detect type| C{Route to<br/>Optimal Processor}
    
    C -->|PNG/JPG/TIFF| C1["🖼️ Vision Processor<br/>VLM + OCR<br/>Native image handling"]
    C -->|CSV| C2["📈 CSV Processor<br/>Table parsing<br/>Data extraction"]
    C -->|AsciiDoc| C3["📖 AsciiDoc Processor<br/>Structured parsing<br/>Tech documentation"]
    C -->|HTML| C4["🌐 HTML Processor<br/>Web extraction<br/>Link tracking"]
    C -->|VTT| C5["🎬 Subtitle Processor<br/>Temporal parsing<br/>Timestamp tracking"]
    C -->|Markdown/Text| C6["📝 Text Processor<br/>Direct processing"]
    C -->|Others| C7["📑 Fallback Docling<br/>MultiFormat handler"]
    
    C1 -->|Optional| CM1["☁️ SageMaker<br/>Remote inference"]
    C1 -->|Memory| CM2["💾 GPU adaptive<br/>loading"]
    
    C1 -->|Extract| C1_OUT["Markdown + metadata"]
    C2 -->|Extract| C2_OUT["Markdown + tables"]
    C3 -->|Extract| C3_OUT["Markdown + structure"]
    C4 -->|Extract| C4_OUT["Markdown + links"]
    C5 -->|Extract| C5_OUT["Markdown + timestamps"]
    C6 -->|Extract| C6_OUT["Markdown"]
    C7 -->|Extract| C7_OUT["Markdown + metadata"]
    
    C1_OUT -->|All output| D["docling_output/<br/>document.md"]
    C2_OUT -->|All output| D
    C3_OUT -->|All output| D
    C4_OUT -->|All output| D
    C5_OUT -->|All output| D
    C6_OUT -->|All output| D
    C7_OUT -->|All output| D
    
    D -->|Also output| E["docling_additional/<br/>tables/images/"]
    
    D -->|Link to| F["Stage 4<br/>Consolidation"]
    E -->|Link to| F
    
    style A fill:#9c27b0
    style B fill:#ba68c8
    style CM1 fill:#ffe0b2
    style CM2 fill:#c8e6c9
    style F fill:#a5d6a7
```

### Key Features of DocumentProcessorV2

✅ **Intelligent Routing**: Automatically detects file type and routes to optimal processor

✅ **SageMaker Support**: Optional remote inference for heavy processing (vision models, etc.)

✅ **GPU Memory Management**: Adaptive loading prevents out-of-memory errors with large files

✅ **Unified Output**: All formats produce consistent markdown + metadata output

✅ **Smart Deduplication**: Skips files already handled by Stage 3b/3c/3d custom parsers

### Stage 3 Processing Decision Flow

```mermaid
graph TD
    A["Input File"] --> B{Has Specialized<br/>Custom Parser?}
    
    B -->|Yes: XLSX/XLSM<br/>in excel_parsed/| C["→ Stage 3b<br/>ExcelPreprocessor"]
    B -->|Yes: DOCX/DOC<br/>in docx_parsed/| D["→ Stage 3c<br/>DocxPreprocessor"]
    B -->|Yes: PDF<br/>in pdf_parsed/| E["→ Stage 3d<br/>PdfPreprocessor"]
    
    B -->|No: Handle in<br/>Stage 3| F["→ DocumentProcessorV2<br/>Unified Router"]
    
    F -->|Intelligent<br/>file-type routing| F1["Select optimal<br/>processor"]
    
    F1 -->|Vision files| F1_V["Vision Processor<br/>(images + OCR)"]
    F1 -->|Data files| F1_D["CSV/Data Processor"]
    F1 -->|Markup files| F1_M["AsciiDoc/HTML<br/>Processor"]
    F1 -->|Other| F1_O["Fallback Docling<br/>Processor"]
    
    F1_V -->|Output| G["stage3_document_processed/"]
    F1_D -->|Output| G
    F1_M -->|Output| G
    F1_O -->|Output| G
    
    C -->|Output| H["stage4_rag_ready/<br/>direct consolidation"]
    D -->|Output| H
    E -->|Output| H
    
    style C fill:#e1bee7
    style D fill:#e1bee7
    style E fill:#e1bee7
    style F fill:#9c27b0
    style F1 fill:#ba68c8
    style G fill:#c8e6c9
    style H fill:#a5d6a7
```

### Stage 3 Output Structure

```
output/stage3_document_processed/
├── document1/                     # From PNG/JPG/etc OCR
│   ├── document1.md               # Main markdown output
│   └── docling_additional/
│       ├── tables/
│       │   └── extracted_tables.md
│       └── images/
│           └── extracted_images.png
│
├── webpage1/                      # From HTML
│   ├── webpage1.md
│   └── docling_additional/
│       └── images/
│           └── embedded_content.png
│
├── documentation/                 # From .adoc AsciiDoc
│   ├── documentation.md
│   └── docling_additional/
│       └── images/
│           └── doc_diagrams.png
│
├── subtitles/                     # From .vtt WebVTT
│   ├── subtitles.md
│   └── docling_additional/
│
├── dataset/                       # From CSV
│   ├── dataset.md
│   └── docling_additional/
│       └── tables/
│           └── parsed_data.md
│
└── logs/
    └── processing.log
```

---

## Stage 3b: Excel Processing (Conditional)

### Purpose
Custom XML-based parsing of Excel files with **table-aware chunking**.

### Trigger Condition
Only runs if `excel_parsed/` directory exists (populated in Stage 1).

### Processing Details

```mermaid
graph TD
    A["excel_parsed/<br/>JSON files"] --> B["ExcelPreprocessor<br/>Custom XML parser"]
    
    B -->|Detect Tables| C["📊 Identify table<br/>boundaries + types"]
    B -->|Smart Chunking| D["📌 Chunk content<br/>chunk_size: 1000 chars<br/>overlap: 200 chars<br/>max_table: 2000 chars"]
    
    C -->|Metadata| E["Track table positions<br/>sheet references"]
    D -->|Output| F["stage4_rag_ready/<br/>doc_id/"]
    E -->|Output| F
    
    F -->|Creates| G["excel_chunks.json<br/>excel_manifest.json<br/>doc_id.md<br/>images/"]
    
    style B fill:#e1bee7
    style D fill:#c8e6c9
    style F fill:#a5d6a7
```

### Output Structure

```
stage4_rag_ready/spreadsheet1/
├── spreadsheet1.md                # Markdown representation
├── excel_chunks.json              # Chunked content {chunks[]}
│                                  # Each chunk tracks: table_id, 
│                                  #                   sheet_name, row_range
├── excel_manifest.json            # Table inventory + structure
└── images/
    └── embedded_charts.png        # Any embedded images
```

---

## Stage 3c: DOCX Processing (Conditional)

### Purpose
Custom XML-based parsing of Word documents with **heading-aware chunking**.

### Trigger Condition
Only runs if `docx_parsed/` directory exists (populated in Stage 1).

### Processing Details

```mermaid
graph TD
    A["docx_parsed/<br/>JSON files"] --> B["DocxPreprocessor<br/>Custom XML parser"]
    
    B -->|Extract Heading<br/>Hierarchy| C["📑 Build heading tree<br/>H1 → H2 → H3 → text"]
    B -->|Smart Chunking| D["📌 Chunk by heading<br/>chunk_size: 1000 chars<br/>overlap: 200 chars<br/>max_table: 2000 chars"]
    
    C -->|Metadata| E["Track heading structure<br/>section references"]
    D -->|Output| F["stage4_rag_ready/<br/>doc_id/"]
    E -->|Output| F
    
    F -->|Creates| G["docx_chunks.json<br/>docx_manifest.json<br/>doc_id.md<br/>images/"]
    
    style B fill:#e1bee7
    style C fill:#b3e5fc
    style D fill:#c8e6c9
    style F fill:#a5d6a7
```

### Output Structure

```
stage4_rag_ready/document1/
├── document1.md                   # Markdown with heading structure
├── docx_chunks.json               # Chunked content {chunks[]}
│                                  # Each chunk tracks: heading_level,
│                                  #                   heading_text, section_id
├── docx_manifest.json             # Heading hierarchy + TOC
└── images/
    └── embedded_images.png        # Any embedded images
```

---

## Stage 3d: PDF Processing (Conditional)

### Purpose
Born-digital custom parser with **heading-aware chunking** for PDFs.

### Trigger Condition
Only runs if `pdf_parsed/` directory exists (populated in Stage 1).

### Processing Details

```mermaid
graph TD
    A["pdf_parsed/<br/>JSON heading-tree"] --> B["PdfPreprocessor<br/>Born-digital parser"]
    
    B -->|Extract Heading<br/>Structure| C["📑 Reconstruct heading tree<br/>from pdf_parsed JSON"]
    B -->|Smart Chunking| D["📌 Chunk by heading<br/>chunk_size: 1000 chars<br/>overlap: 200 chars"]
    
    C -->|Metadata| E["Track page references<br/>section positions"]
    D -->|Output| F["stage4_rag_ready/<br/>doc_id/"]
    E -->|Output| F
    
    F -->|Creates| G["pdf_chunks.json<br/>pdf_manifest.json<br/>doc_id.md<br/>images/"]
    
    style B fill:#e1bee7
    style C fill:#ffccbc
    style D fill:#c8e6c9
    style F fill:#a5d6a7
```

### Output Structure

```
stage4_rag_ready/report.pdf/
├── report.pdf.md                  # Markdown with heading structure
├── pdf_chunks.json                # Chunked content {chunks[]}
│                                  # Each chunk tracks: page_number,
│                                  #                   heading_level, section_id
├── pdf_manifest.json              # Page index + heading hierarchy
└── images/
    └── page_3_extracted.png       # Extracted page images
```

---

## Stage 4: RAG-Ready Consolidation

### Purpose
Combine all Stage 3 outputs (Docling, Excel, DOCX, PDF) plus media data into unified RAG-ready document folders.

### Consolidation Logic

```mermaid
graph TD
    A["stage3_document_processed/<br/>Stage 3 outputs"] --> B["Stage4Consolidator"]
    C["stage2_media_processed/<br/>Media transcripts/frames"] --> B
    
    B -->|Per-document<br/>folder| D["Consolidate all<br/>outputs"]
    
    D -->|Text| D1["Merge chunks<br/>from all sources"]
    D -->|Media| D2["Link transcripts<br/>+ extracted frames"]
    D -->|Images| D3["Collect all image<br/>files + metadata"]
    D -->|Tables| D4["Include table<br/>chunks"]
    
    D1 -->|Output| E["stage4_rag_ready/<br/>document_id/"]
    D2 -->|Output| E
    D3 -->|Output| E
    D4 -->|Output| E
    
    E -->|Structure| F["chunks.json<br/>(text retrieval)"]
    E -->|Structure| G["images/<br/>(image retrieval)"]
    E -->|Structure| H["metadata.json<br/>(provenance)"]
    E -->|Structure| I["transcripts/<br/>(media content)"]
    
    style E fill:#c8e6c9
    style F fill:#a5d6a7
    style G fill:#a5d6a7
```

### Stage 4 Output Structure

```
output/stage4_rag_ready/
├── document_id1/
│   ├── chunks.json                # [{chunk_id, text, start_pos, chunk_type, 
│   │                              #   source: docx|pdf|excel|media, ...}]
│   ├── metadata.json              # Document metadata + chunk mapping
│   ├── images/
│   │   ├── image_001.jpg
│   │   ├── image_001_metadata.json
│   │   └── ...
│   ├── transcripts/               # Links to stage2 media outputs
│   │   └── video1_transcript.md
│   ├── tables/
│   │   ├── table_001.md
│   │   └── ...
│   └── pdf.pdf                    # Original PDF (if available)
│
├── document_id2/
│   └── ...
│
└── ...
```

---

## Indexing Pipeline

### Purpose
Create searchable indexes from RAG-ready content using three systems: dense text embeddings (Qdrant), keyword search (BM25), and image embeddings (ColQwen) for visual retrieval.

### Two Retrieval Systems

```mermaid
graph TD
    A["stage4_rag_ready/<br/>chunks + images"] --> B["📑 Text Index"]
    A --> C["🖼️ Image Index"]
    
    B -->|Extract text<br/>chunks| B1["Text chunks"]
    B1 -->|sentence-transformers<br/>`all-MiniLM-L6-v2`| B2["Dense vectors"]
    B2 -->|Store in| B3["🗂️ Qdrant<br/>edu_text_chunks"]
    
    B1 -->|BM25<br/>Algorithm| B4["Keyword index"]
    B4 -->|Pickle file| B5["📦 bm25_index.pkl"]
    
    B3 -->|Hybrid fusion<br/>alpha=0.5| B6["⚙️ Hybrid Retriever"]
    B5 -->|Hybrid fusion| B6
    
    C -->|Extract images<br/>per page| C1["Page images"]
    C1 -->|Render PDF<br/>to images<br/>150 DPI| C2["📸 Image files"]
    C2 -->|ColQwen<br/>Multivectors| C3["🎨 Image embeddings"]
    C3 -->|Store in| C4["🗂️ Qdrant<br/>edu_image_pages"]
    
    B6 -->|Create| D["✨ Index ready<br/>documents.json"]
    C4 -->|Create| D
    
    style B6 fill:#c8e6c9
    style C4 fill:#ffccbc
    style D fill:#fff9c4
```

### Reranking (Globally Disabled)

**Current Status**: Reranking is **globally disabled** (`SKIP_RERANKER=true` by default) for latency optimization. The reranker code is retained in the codebase for fast rollback if needed, but is not invoked during search.

```mermaid
graph TD
    A["Retrieve top K<br/>BM25 + Dense"] --> B["Return top K<br/>Results"]
    
    B -->|Note| C["⚠️ Reranker disabled<br/>globally for performance<br/>No re-ranking applied"]
    
    B -->|Return to| D["Merged results<br/>(text + images)"]
    
    style C fill:#ffe0b2
    style D fill:#c8e6c9
```

**Historical context**: Earlier implementations supported optional reranking using `bge-large`, `bge-base`, or `minilm-l12` models, but this was disabled globally in favor of latency optimization. The `skip_reranker` parameter in the search API is deprecated and ignored.

### Indexing Output Artifacts

```
output/indexing/
├── documents.json                 # Document metadata + chunk inventory
├── qdrant_collections/
│   ├── edu_text_chunks            # Text embeddings (Qdrant)
│   │   └── points: 10,000+ points
│   └── edu_image_pages            # Image embeddings (Qdrant)
│       └── points: 5,000+ points
└── bm25_indexes/
    └── user_default/
        └── bm25_index.pkl         # BM25 keyword index (pickle)
```

---

## Search & Retrieval Pipeline

### Purpose
Retrieve relevant content from indexes and optionally generate AI-powered answers.

### Search Flow

```mermaid
graph TD
    A["🔍 User Query"] --> A1{Search Scope?}
    
    A1 -->|text only| A2["Text index only"]
    A1 -->|image only| A3["Image index only"]
    A1 -->|both| A4["Text + Image indexes"]
    
    A2 --> B{Retriever Type?}
    A3 --> B
    A4 --> B
    
    B -->|BM25| C["Keyword search<br/>on text index"]
    B -->|Dense| D["Semantic search<br/>on Qdrant dense"]
    B -->|Hybrid| E["Combine BM25<br/>+ Qdrant (alpha=0.5)"]
    
    C -->|Top K| F["Text results<br/>with scores"]
    D -->|Top K| F
    E -->|Top K| F
    
    A4 -->|if images| G["🎨 ColQwen<br/>Image search<br/>on image index"]
    
    G -->|Top K images| H["Image results<br/>+ page metadata"]
    
    F -->|Merge| K["Combined<br/>results"]
    H -->|Merge| K
    
    K -->|retrieval_only| M["📤 Return results<br/>text + images"]
    K -->|retrieval_generation| L["🤖 LLM Generation<br/>with context<br/>(GPT-4o-mini/Claude)"]
    
    L -->|Generate| N["💡 Answer<br/>with citations"]
    N -->|Return| M
    
    style F fill:#c8e6c9
    style H fill:#ffccbc
    style K fill:#a5d6a7
    style L fill:#fff9c4
    style M fill:#b2dfdb
```

### Response Structure

```json
{
  "query": "What are the key findings?",
  "text_results": [
    {
      "chunk": "The analysis shows...",
      "source_path": "document1.md",
      "storage_uri": "s3://bucket/path/...",
      "score": 0.95,
      "chunk_type": "docx | pdf | excel | media"
    }
  ],
  "image_results": [
    {
      "page": 5,
      "source_path": "document.pdf",
      "confidence": 0.88
    }
  ],
  "answer": "Generated answer using retrieved content...",
  "generation_config": {
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "max_tokens": 2000
  }
}
```

---

## Storage Architecture

### Local vs Cloud Storage

```mermaid
graph TB
    A["📤 Upload"] --> B{Storage Backend}
    
    B -->|Local| C["💾 Local Disk"]
    C --> D["backend/input/"]
    C --> E["backend/output/"]
    D -->|Processing| E
    E -->|Stages 1-4| F["All output<br/>in backend/output/"]
    
    B -->|S3| G["☁️ AWS S3"]
    G --> H["S3: Originals<br/>Bucket"]
    G --> I["S3: Processed<br/>Bucket"]
    H -->|Download on<br/>process| J["Temp: Local<br/>workspace"]
    J -->|Processing| K["Local stages<br/>1-4 output"]
    K -->|Upload when<br/>done| I
    
    F -->|Ready for| L["🔍 Indexing"]
    I -->|Ready for| L
    
    style C fill:#b3e5fc
    style G fill:#ffe0b2
    style L fill:#fff9c4
```

**Explanation:**
- **Local Storage**: All processing happens on local disk (`backend/input/` → `backend/output/stages/*`)
- **S3 Storage**: Two buckets separate originals from processed outputs. Pipeline downloads to temp workspace, processes locally, then uploads results to S3 processed bucket. Both approaches feed the same indexing pipeline.

### Multi-User Isolation

```
S3 Key Structure (when S3_USER_ISOLATION=true):
users/{user_id}/documents/{document_id}/jobs/{job_id}/processing/
  ├── stage1_normalized/
  ├── stage2_media_processed/
  ├── stage3_document_processed/
  └── stage4_rag_ready/

Per-user isolation:
- Each user has isolated temp workspace during processing
- S3 prefixes prevent cross-user data access
- Optional: Qdrant collections per user (QDRANT_ISOLATE_BY_USER=true)
```

---

## Summary Table: All 7 Stages & Processing

| Stage | Name | Input | Processor(s) | Output | Special Features |
|-------|------|-------|--------------|--------|------------------|
| **1** | Normalization | Raw files (all types) | DocumentNormalizer | Normalized PDFs/JSON/MD in separate folders | Format detection + conversion |
| **2** | Media Processing | Video/Audio files | MediaProcessor | Transcripts, frames, audio, metadata | Noise reduction, dedup, frame-chunk binding |
| **3** | Document Processing (V2 Router) | Normalized PDFs, Markdown, original files (except handled by 3b/3c/3d) | DocumentProcessorV2 (Unified Router) | docling_output/ (.md) + docling_additional/ | Intelligent file-type routing. Supports 10 formats (PDF, DOCX, XLSX, PPT, HTML, CSV, AsciiDoc, VTT, Images, MD). SageMaker support + GPU memory management. Smart dedup skips files in 3b/3c/3d. |
| **3b** | Excel Processing | excel_parsed/ JSON files | ExcelPreprocessor (custom XML parser) | Direct to stage4_rag_ready/ | Table-aware chunking (max 2000 characters), sheet tracking |
| **3c** | DOCX Processing | docx_parsed/ JSON files | DocxPreprocessor (custom XML parser) | Direct to stage4_rag_ready/ | Heading-aware chunking, heading hierarchy tracking |
| **3d** | PDF Processing | pdf_parsed/ JSON files | PdfPreprocessor (born-digital parser) | Direct to stage4_rag_ready/ | Heading-aware chunking, page-level tracking |
| **4** | Consolidation | All Stage 3 outputs + Stage 2 media | Stage4Consolidator | stage4_rag_ready/ with chunks + images + metadata | Merges all sources, links media to text, creates per-document folders |
| **Index** | Indexing | RAG-ready documents | Qdrant + BM25 + ColQwen | edu_text_chunks + edu_image_pages collections | Text (dense + keyword) + image indexing. Optional reranking (disabled by default). |
| **Search** | Retrieval & Generation | Query + indexes | TextSearchService + ImageRetriever + LLM | Results with citations | Hybrid fusion, optional LLM generation, multimodal output |

---

## Key Design Principles

✅ **Unified Router (V2):** DocumentProcessorV2 intelligently routes different file types to optimal processors

✅ **Conditional Processing:** Stage 3b/3c/3d variants only run if their specialized input is detected

✅ **Custom XML Parsers:** DOCX, Excel, and PDF get specialized parsing (heading-aware, table-aware, heading-hierarchy)

✅ **Media Integration:** Transcripts and frames are unified with document chunks via timestamp binding

✅ **Metadata Tracking:** All outputs preserve provenance and source information for citations

✅ **Multi-Modal Retrieval:** Text + image search work in parallel with optional LLM generation

✅ **Storage Agnostic:** Works with local disk or AWS S3 with identical logical structure

✅ **Cloud-Ready:** SageMaker support for remote inference + GPU memory management for large files

---

## 📊 Diagram Classification: Presentation vs Appendix

### **ESSENTIAL DIAGRAMS FOR PRESENTATION** (Must Include)

These diagrams are critical for understanding the system in a capstone/conference presentation:

1. **Pipeline Architecture Overview** (Early section)
   - Shows the complete system flow: Upload → 7-Stage Processing → Indexing → Search/Retrieval
   - Gives audience overview of the entire pipeline lifecycle
   - **Why:** Establishes the system's purpose and scope

2. **Complete Pipeline Architecture (7-Stage Model)**
   - Shows all stages in order: 1 (Normalization) → 2 (Media) → 3 (Docling) → 3b/3c/3d (Custom parsers) → 4 (Consolidation)
   - Shows how Stage 3 splits into 4 parallel paths
   - **Why:** Explains the sophisticated multi-path processing architecture

3. **Stage 1: File Type Routing Diagram**
   - Shows how different file types (DOCX, Excel, PDF, Images, etc.) are routed to different processors
   - **Why:** Demonstrates intelligent file-type handling and the breadth of supported formats (10+ types)

4. **Stage 2: Media Processing Flow**
   - Shows audio extraction, noise reduction, transcription, frame extraction, frame deduplication
   - **Why:** Highlights the sophisticated media handling with noise reduction and deduplication

5. **Indexing Pipeline: Text and Image Indexing**
   - Shows dual indexing: text (dense + BM25) + image (ColQwen)
   - Shows storage in Qdrant collections
   - **Why:** Demonstrates the multimodal retrieval capability

6. **Search & Retrieval Pipeline**
   - Shows search options (BM25/Dense/Hybrid), image retrieval, optional LLM generation
   - Shows search_scope and mode options
   - **Why:** Demonstrates the flexible retrieval system with optional AI generation

### **APPENDIX DIAGRAMS** (Reference/Supporting Material)

These diagrams provide details but are not essential for the main presentation narrative:

1. **Stage 1 Processing Details** - Text table details of all file type handlers
2. **Stage 3 Supported Input Formats** - Detailed list of 10 supported formats
3. **Stage 3 Smart Deduplication Logic** - Technical deduplication strategy (complex for presentation)
4. **DocumentProcessorV2 Unified Router** - Technical implementation details (too low-level for presentation)
5. **File Type Routing (Logic Flow)** - Alternative representation of routing (if already showing Stage 1 diagram)
6. **Stage 3 Processing Decision Flow** - Alternative detail diagram
7. **Stage 3b/3c/3d Output Structures** - Table details of Excel/DOCX/PDF outputs (reference only)
8. **Stage 4 Consolidation Process** - Technical consolidation details
9. **Indexing Output Artifacts** - Directory structure (technical detail)
10. **Reranking (Globally Disabled)** - Historical context on reranking (now disabled)
11. **Response Structure** - JSON schema (API detail, not needed for general presentation)
12. **Storage Architecture** - Local vs S3 comparison (infrastructure detail)
13. **Processing Timeline** - Sequential execution explanation (technical detail)

### **PRESENTATION STRATEGY**

For a 20-25 minute capstone presentation:

1. **Opening (2 min):** Use the "Pipeline Architecture Overview" to show the system flow
2. **Architecture Deep-Dive (5 min):** 
   - Show "Complete Pipeline Architecture (7-Stage Model)" to explain the staged approach
   - Show "Stage 1 File Type Routing" to demonstrate format handling
3. **Technical Highlights (3 min):**
   - Show "Stage 2 Media Processing Flow" for media intelligence
   - Show "Indexing Pipeline" to explain retrieval capabilities
4. **Retrieval & Results (2 min):** Show "Search & Retrieval Pipeline" with generation
5. **Appendix:** Include detailed diagrams in presentation appendix for Q&A reference

**Total essential diagrams for presentation:** 6 core diagrams + supporting tables  
**Total appendix diagrams for reference:** 13 detail/technical diagrams

---

**Document prepared:** May 2026  
**Scope:** Complete AI Service pipeline architecture with all 7 processing stages  
**Verification:** All claims verified against Phase 2 implementation codebase
