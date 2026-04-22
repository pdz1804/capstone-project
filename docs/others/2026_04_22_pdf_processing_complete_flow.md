# 📄 PDF PROCESSING COMPLETE FLOW: V2.1 with SageMaker

**Date:** 2026-04-22  
**Focus:** What happens to PDFs from upload to RAG-ready output

---

## 🔄 COMPLETE PIPELINE FLOW

### Stage 1: Normalization
```
📥 INPUT: Any file format (PDF, DOCX, XLSX, PPTX, HTML, etc.)

├─ Normalizer processes file
│  ├─ Detects file type
│  ├─ Applies appropriate normalizer
│  └─ Creates normalized outputs
│
└─ STAGE 1 OUTPUTS:
   ├─ normalized_pdfs/           ← PDFs ready for Docling
   ├─ normalized_markdown/       ← Already-markdown files
   ├─ excel_parsed/              ← Excel JSON (pre-processed, skips Docling)
   ├─ docx_parsed/               ← DOCX JSON (pre-processed, skips Docling)
   ├─ pdf_parsed/                ← PDF JSON (pre-processed, skips Docling)
   ├─ original_files/            ← Original unmodified files
   └─ normalization_metadata/    ← PDF classification metadata
```

**Example: If input is PDF**
- Already PDF → Copy to normalized_pdfs/
- Scan classification → Create pdf_classification.json

**Example: If input is DOCX**
- DOCX → Parsed by DocxParser → docx_parsed/docx_file.json
- DOCX also converted to PDF → normalized_pdfs/docx_file.pdf

---

### Stage 3: Document Processing (V2.1 Smart Router)

```
📥 INPUT (from Stage 1):
   - normalized_pdfs/*.pdf
   - normalized_markdown/*.md
   - original_files/*
   - (pre-parsed files already in excel_parsed/, docx_parsed/, pdf_parsed/)

V2.1 Router Decision Tree:
├─ File already pre-processed?
│  ├─ Excel JSON exists → ✅ Skip (already done)
│  ├─ DOCX JSON exists → ✅ Skip (already done)
│  ├─ PDF JSON exists → ✅ Skip (already done)
│  └─ No → Continue to routing
│
├─ Route by file type:
│  ├─ .xlsx / .xls / .xlsm
│  │  └─ xlsx_reader_v2 (custom XML parser)
│  │     ✅ Outputs: {file}.md + {file}_parsed.json
│  │
│  ├─ .docx / .doc
│  │  └─ docx_reader_v2 (custom parser)
│  │     ✅ Outputs: {file}.md + {file}_parsed.json
│  │
│  ├─ .pptx / .ppt
│  │  └─ pptx_reader (custom parser)
│  │     ✅ Outputs: {file}.md + content_tree JSON
│  │
│  ├─ .pdf
│  │  └─ Check classification metadata
│  │     ├─ If "born_digital" → pdf_reader (custom)
│  │     │  ✅ Outputs: {file}.md + {file}_parsed.json
│  │     └─ Else or no metadata → docling (next step)
│  │
│  └─ Everything else (.md, .html, .csv, .txt, images, etc)
│     └─ docling (default)
│
└─ Docling Path (for PDFs without born_digital + other formats):
   ├─ Check: use_sagemaker_for_docling?
   │  ├─ YES → _run_sagemaker_docling()
   │  │  ├─ Send PDF to SageMaker endpoint
   │  │  ├─ Response: {"markdown": "...", "additional_files": {...}}
   │  │  └─ ⚠️ Config mismatch: SageMaker has VLM=false, images=false by default!
   │  │
   │  └─ NO → _run_docling() (Local)
   │     ├─ Try primary converter (GPU)
   │     │  ├─ If success → return result
   │     │  └─ If CUDA OOM:
   │     │     ├─ Clean GPU memory
   │     │     ├─ Set disable_ocr_on_gpu_pressure = true
   │     │     └─ Try fallback converter
   │     └─ Return result or raise error
   │
   └─ ✅ Outputs: {file}.md + {file}_metadata.json + docling_additional/

📤 STAGE 3 OUTPUTS:
   stage3_document_processed/
   ├── file1/
   │   ├── file1.md                    ← Markdown content
   │   ├── file1_metadata.json         ← Processing metadata
   │   ├── file1_parsed.json           ← (if custom reader)
   │   └── docling_additional/         ← (if Docling)
   │       ├── images/                 ← Extracted images
   │       ├── tables/                 ← Extracted tables
   │       └── ...
   ├── file2/
   └── file3/
```

---

## 🎯 PDF SPECIFIC PROCESSING

### Scenario 1: Scanned PDF (born_digital = False)
```
Input: scan.pdf (11 pages, scanned document)

Stage 1:
  └─ normalized_pdfs/scan.pdf
  └─ normalization_metadata/scan_pdf_classification.json
     └─ {"pdf_type": "scanned"}

Stage 3 V2.1 Router:
  ├─ Check classification: pdf_type = "scanned" (not "born_digital")
  ├─ Route to: docling
  │
  ├─ If use_sagemaker_for_docling = False (LOCAL):
  │  ├─ Try primary Docling converter on GPU
  │  ├─ Page 1-5: CUDA OOM ❌
  │  ├─ GPU cleanup activated
  │  ├─ OCR disabled (due to GPU pressure)
  │  └─ Partial or failed result ❌
  │
  └─ If use_sagemaker_for_docling = True (SAGEMAKER):
     ├─ Send scan.pdf + base64 to endpoint
     ├─ Endpoint processes all 11 pages ✅
     ├─ Returns: markdown + images (if configured) + tables (if configured)
     └─ Result: SUCCESS ✅

Stage 4:
  └─ scan/
     ├── scan.md                    ← Full extracted text
     ├── scan_metadata.json         ← Metadata
     └── docling_additional/        ← Images/tables (if SageMaker had VLM=true)
```

### Scenario 2: Born Digital PDF
```
Input: forms.pdf (PDF created from data, not scanned)

Stage 1:
  └─ normalized_pdfs/forms.pdf
  └─ normalization_metadata/forms_pdf_classification.json
     └─ {"pdf_type": "born_digital"}

Stage 3 V2.1 Router:
  ├─ Check classification: pdf_type = "born_digital" ✅
  ├─ Route to: pdf_reader (custom parser)
  └─ Skip Docling entirely ✅ (no GPU needed)

Output:
  └─ forms/
     ├── forms.md                   ← Text extracted
     ├── forms_parsed.json          ← Parsed structure
     └── forms_metadata.json        ← Metadata

Result: Fast, efficient, no GPU/CUDA issues
```

### Scenario 3: PDF That Was Converted from DOCX
```
Input: report.docx

Stage 1:
  ├─ DocxParser processes → docx_parsed/report.json ✅
  ├─ Also converts → normalized_pdfs/report.pdf
  └─ Metadata shows: PDF created from DOCX

Stage 3 V2.1 Router:
  ├─ Check: docx_parsed/report.json exists?
  ├─ YES → Skip rest, already processed ✅
  └─ Result: docx_parsed JSON reused, no re-processing

Output:
  └─ report/
     ├── report.md                  ← From custom DOCX parser
     ├── report_parsed.json         ← From custom DOCX parser
     └── report_metadata.json

Result: Efficient, uses best parser for each format
```

---

## 📊 CONFIG IMPACT TABLE

### When Processing PDFs with SageMaker

| Setting | Local Value | SageMaker Default | Result |
|---------|-------------|-------------------|--------|
| enable_vlm | TRUE | FALSE ⚠️ | No image descriptions |
| export_images | TRUE | FALSE ⚠️ | No images extracted |
| export_tables | TRUE | FALSE ⚠️ | No tables extracted |
| enable_ocr | TRUE | TRUE | Text extracted ✅ |

**⚠️ WORKAROUND:** Redeploy SageMaker endpoint with env vars:
```bash
DOCLING_ENABLE_VLM=true
DOCLING_EXPORT_IMAGES=true
DOCLING_EXPORT_TABLES=true
```

---

## 🔀 ROUTING DECISION MATRIX

| File Type | Extension | Route | Processor | GPU Needed | Output Format |
|-----------|-----------|-------|-----------|-----------|----------------|
| **DOCX** | .docx | Custom | docx_reader_v2 | NO | .md + .json |
| **XLSX** | .xlsx | Custom | xlsx_reader_v2 | NO | .md + .json |
| **PPTX** | .pptx | Custom | pptx_reader | NO | .md + .json |
| **PDF (Born Digital)** | .pdf | Custom | pdf_reader | NO | .md + .json |
| **PDF (Scanned)** | .pdf | Docling Local | Docling GPU | YES | .md + images + tables |
| **PDF (Scanned)** | .pdf | Docling SageMaker | SageMaker | NO (remote) | .md + (images + tables if configured) |
| **Markdown** | .md | Docling | Docling GPU | YES | .md |
| **HTML** | .html | Docling | Docling GPU | YES | .md + images |
| **Images** | .png/.jpg | Docling | Docling GPU | YES | .md (captions) |
| **CSV** | .csv | Docling | Docling CPU | NO | .md |

---

## 📁 FINAL OUTPUT FOLDER STRUCTURE

```
stage4_rag_ready/
├── docx_file/
│   ├── docx_file.md                    ← From custom reader
│   ├── docx_file_parsed.json           ← Structure
│   ├── docx_chunks.json                ← For RAG indexing
│   ├── docx_manifest.json              ← Metadata
│   └── images/                         ← Embedded images
│
├── scanned_pdf/
│   ├── scanned_pdf.md                  ← From Docling
│   ├── scanned_pdf_metadata.json       ← Processing metadata
│   ├── scanned_pdf_chunks.json         ← For RAG indexing
│   ├── docling_additional/
│   │   ├── images/                     ← Extracted images
│   │   │   ├── image_001.png
│   │   │   ├── image_001.txt           ← VLM description
│   │   │   └── ...
│   │   ├── tables/                     ← Extracted tables
│   │   │   ├── table_001.csv
│   │   │   └── ...
│   │   └── metadata.json               ← Additional metadata
│   └── docling_additional_chunks.json  ← Chunks from additional files
│
├── born_digital_pdf/
│   ├── born_digital_pdf.md             ← From pdf_reader
│   ├── born_digital_pdf_parsed.json    ← Parsed structure
│   ├── born_digital_pdf_metadata.json  ← Metadata
│   └── (no additional files - born digital has clean text)
│
└── markdown_file/
    ├── markdown_file.md                ← Pass-through from Docling
    ├── markdown_file_chunks.json       ← Chunks for RAG
    └── markdown_file_metadata.json     ← Metadata
```

---

## ⚡ KEY DECISION POINTS IN V2.1

### 1. GPU Memory Management
```
if layout_model_oom_encountered and disable_ocr_on_gpu_pressure:
    enable_ocr = False  # Save GPU for retry
```

### 2. SageMaker Switch
```
if use_sagemaker_for_docling:
    return _run_sagemaker_docling(file_path)
else:
    return _run_docling_local(file_path)
```

### 3. Custom Reader Pre-check
```
if pre_processed_excel_json_exists:
    skip_docling()  # Already done in Stage 1
```

---

## 🚀 PERFORMANCE CHARACTERISTICS

| Path | Time | GPU | Parallel | Reliability |
|------|------|-----|----------|-------------|
| Custom readers (DOCX/XLSX/PPTX) | 2-10s | NO | YES | ✅ High |
| Born Digital PDF | 5-15s | NO | YES | ✅ High |
| Docling Local (GPU) | 10-120s | YES | NO | ⚠️ Medium (OOM risk) |
| Docling SageMaker | 30-180s | NO | YES | ✅ High |
| Scanned PDF (Docling Local) | 30-180s | YES | NO | ❌ Low (OOM likely) |
| Scanned PDF (Docling SageMaker) | 40-200s | NO | YES | ✅ High |

---

**Summary:** V2.1 optimizes by using specialized readers first, then falls back to Docling (local or SageMaker) for complex formats. SageMaker provides scalability but requires env var configuration to match local feature set.

---

**Generated:** 2026-04-22  
**Project:** bk_mind Phase 2  
**Branch:** develop
