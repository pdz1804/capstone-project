# 📋 PIPELINE RESTRUCTURING IMPLEMENTATION PLAN

**Date**: November 23, 2025  
**Goal**: Restructure the 3-stage pipeline to properly separate normalization, media processing, and document processing, then create a unified Stage 4 output ready for RAG.

---

## 🎯 OBJECTIVES

1. **Stage 1**: Only normalize files to PDF (no markdown conversion except TXT→MD)
2. **Stage 2**: Process video/audio → markdown transcripts only
3. **Stage 3**: Process ALL unprocessed files through Docling
4. **Stage 4**: Create unified output structure for RAG pipeline

---

## ✅ DOCLING FORMAT SUPPORT VERIFICATION

Based on analysis of `docling/datamodel/base_models.py`, Docling **NATIVELY SUPPORTS**:

| Format | Extensions | Docling Support | Notes |
|--------|-----------|-----------------|-------|
| PDF | `.pdf` | ✅ `InputFormat.PDF` | Full support |
| DOCX | `.docx`, `.dotx`, `.docm`, `.dotm` | ✅ `InputFormat.DOCX` | Full support |
| XLSX | `.xlsx`, `.xlsm` | ✅ `InputFormat.XLSX` | Full support |
| PPTX | `.pptx`, `.potx`, `.ppsx`, `.pptm`, `.potm`, `.ppsm` | ✅ `InputFormat.PPTX` | Full support |
| Markdown | `.md` | ✅ `InputFormat.MD` | Full support |
| AsciiDoc | `.adoc`, `.asciidoc`, `.asc` | ✅ `InputFormat.ASCIIDOC` | Full support |
| HTML/XHTML | `.html`, `.htm`, `.xhtml` | ✅ `InputFormat.HTML` | Full support |
| CSV | `.csv` | ✅ `InputFormat.CSV` | Full support |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp` | ✅ `InputFormat.IMAGE` | Full support |
| WebVTT | `.vtt` | ✅ `InputFormat.VTT` | Full support |
| Audio/Video | `.wav`, `.mp3`, `.m4a`, `.aac`, `.ogg`, `.flac`, `.mp4`, `.avi`, `.mov` | ✅ `InputFormat.AUDIO` | Full support |
| XML (JATS) | `.xml`, `.nxml` | ✅ `InputFormat.XML_JATS` | Special format |
| XML (USPTO) | `.xml`, `.txt` | ✅ `InputFormat.XML_USPTO` | Special format |

**Result**: ✅ All required formats are supported by Docling!

---

## 📐 STAGE-BY-STAGE DESIGN

### **STAGE 1: Document Normalization** (Modified)

**Purpose**: Prepare files for Docling processing by normalizing complex formats to PDF.

**Input**: `input/` (raw files)  
**Output**: `output/stage1_normalized/`

#### What Stage 1 Should Do:

```
INPUT FILES                           ACTION                    OUTPUT LOCATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Office Documents:
├─ .docx, .pptx, .xlsx         →    Convert to PDF        →   normalized_pdfs/
│                                    Copy original         →   original_files/

Images:
├─ .png, .jpg, .jpeg, .tiff,   →    Convert to PDF        →   normalized_pdfs/
│  .bmp, .webp                       Copy original         →   original_files/

Web Documents:
├─ .html, .htm, .xhtml         →    Convert to PDF        →   normalized_pdfs/
│                                    Copy original         →   original_files/

Text Files:
├─ .txt                        →    Convert to .md        →   normalized_markdown/
├─ .md                         →    Copy as-is            →   normalized_markdown/

Already PDF:
├─ .pdf                        →    Copy as-is            →   normalized_pdfs/
│                                    Copy to originals     →   original_files/

CSV/Spreadsheets:
├─ .csv                        →    Keep original         →   original_files/

AsciiDoc:
├─ .adoc, .asciidoc, .asc      →    Keep original         →   original_files/

WebVTT:
├─ .vtt                        →    Keep original         →   original_files/

Media (skip - handled in Stage 2):
├─ .mp4, .avi, .mov, .mp3, etc →    SKIP                  →   (Stage 2 handles)
```

#### Output Structure:
```
output/stage1_normalized/
├── normalized_pdfs/              # PDFs for image-based RAG
│   ├── research_paper.pdf        # (converted from HTML)
│   ├── presentation.pdf          # (converted from PPTX)
│   ├── document.pdf              # (converted from DOCX)
│   ├── chart.pdf                 # (converted from PNG)
│   └── original_file.pdf         # (copied as-is)
│
├── original_files/               # Original files for Stage 3 Docling processing
│   ├── research_paper.html
│   ├── presentation.pptx
│   ├── document.docx
│   ├── chart.png
│   ├── original_file.pdf
│   ├── data.csv
│   └── guide.asciidoc
│
├── normalized_markdown/          # Only TXT→MD conversions
│   ├── notes.md                  # (converted from notes.txt)
│   └── readme.md                 # (copied as-is)
│
└── normalization_metadata/
    └── normalization_stats.json
```

#### Key Changes:
1. ❌ **REMOVE**: Markdown conversion for DOCX, PPTX, HTML, CSV, Excel
2. ❌ **REMOVE**: Text extraction to markdown in Stage 1
3. ✅ **KEEP**: PDF generation for image-based RAG
4. ✅ **KEEP**: Original file preservation for Docling
5. ✅ **ADD**: Support for AsciiDoc, WebVTT (copy to original_files/)

---

### **STAGE 2: Media Processing** (Modified)

**Purpose**: Extract audio and transcripts from video/audio files.

**Input**: `input/` (video/audio files)  
**Output**: `output/stage2_media_processed/`

#### What Stage 2 Should Do:

```
INPUT FILES                           ACTION                    OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Video Files:
├─ .mp4, .avi, .mov, etc.      →    Extract audio         →   extracted_audio/
│                              →    Transcribe (ASR)      →   transcripts/*.json
│                              →    Convert to markdown   →   transcripts/*.md
│                              →    Generate subtitles    →   transcripts/*.srt, *.vtt
│                              →    Extract frames        →   extracted_frames/

Audio Files:
├─ .mp3, .wav, .aac, etc.      →    Transcribe (ASR)      →   transcripts/*.json
                               →    Convert to markdown   →   transcripts/*.md
                               →    Generate subtitles    →   transcripts/*.srt, *.vtt
```

#### Output Structure:
```
output/stage2_media_processed/
├── extracted_audio/
│   └── lecture_video.wav
│
├── transcripts/
│   ├── lecture_video.json        # Full transcript with timestamps
│   ├── lecture_video.md          # ⭐ NEW: Markdown format for Stage 3
│   ├── lecture_video.srt         # Subtitle format
│   └── lecture_video.vtt         # WebVTT format
│
├── extracted_frames/
│   └── lecture_video/
│       ├── frame_0001.jpg
│       ├── frame_0002.jpg
│       └── ...
│
└── media_metadata/
    └── media_processing_stats.json
```

#### Key Changes:
1. ✅ **ADD**: Generate `.md` markdown format from transcripts
2. ✅ **KEEP**: JSON, SRT, VTT formats
3. ✅ **KEEP**: Frame extraction
4. ❌ **REMOVE**: No processing of non-media files

---

### **STAGE 3: Document Processing with Docling** (Major Redesign)

**Purpose**: Process ALL unprocessed files through Docling for unified markdown output.

**Input Sources**:
1. `stage1_normalized/original_files/` (original quality files)
2. `stage1_normalized/normalized_pdfs/` (converted PDFs for OCR)
3. `stage1_normalized/normalized_markdown/` (TXT→MD, original MD)
4. `stage2_media_processed/transcripts/*.md` (video transcripts as markdown)

**Output**: `output/stage3_document_processed/`

#### What Stage 3 Should Process:

```
INPUT SOURCES                          PROCESSING                OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
From original_files/:
├─ .pdf                          →    Docling (OCR+VLM)    →   file/file.md
├─ .docx, .pptx, .xlsx           →    Docling              →   file/file.md
├─ .html, .htm, .xhtml           →    Docling              →   file/file.md
├─ .png, .jpg, .jpeg, ...        →    Docling (OCR+VLM)    →   file/file.md
├─ .csv                          →    Docling              →   file/file.md + tables
├─ .asciidoc, .adoc, .asc        →    Docling              →   file/file.md
├─ .vtt                          →    Docling              →   file/file.md

From normalized_pdfs/:
├─ converted PDFs                →    Docling (OCR+VLM)    →   file/file.md

From normalized_markdown/:
├─ .md (original + TXT→MD)       →    Docling              →   file/file.md

From transcripts/:
├─ .md (video transcripts)       →    Docling              →   file/file.md
```

#### Output Structure:
```
output/stage3_document_processed/
├── research_paper/
│   ├── research_paper_metadata.json
│   ├── research_paper.md            # Main markdown output
│   ├── table_000.csv                # Extracted tables
│   ├── table_000.md
│   ├── image_001.png                # Extracted images (filtered by size)
│   └── image_002.png
│
├── presentation/
│   ├── presentation_metadata.json
│   ├── presentation.md
│   └── image_001.png
│
├── lecture_video/
│   ├── lecture_video_metadata.json
│   └── lecture_video.md             # From transcript
│
└── logs/
    └── batch_summary_*.json
```

#### Key Changes:
1. ✅ **ADD**: Process normalized PDFs (for better OCR)
2. ✅ **ADD**: Process video transcript markdown files
3. ✅ **ADD**: Support for AsciiDoc, WebVTT, CSV, XLSX formats
4. ✅ **KEEP**: Image extraction with size filtering
5. ✅ **KEEP**: Table extraction
6. ❌ **REMOVE**: Don't process SRT, VTT, JSON, TXT transcript files (only .md)

---

### **STAGE 4: RAG-Ready Output** (NEW STAGE)

**Purpose**: Create unified output structure ready for chunking and embedding.

**Input**: `output/stage3_document_processed/`  
**Output**: `output/stage4_ready/`

#### Consolidation Logic:

```
For each document processed in Stage 3:
1. Check if normalized PDF exists in stage1_normalized/normalized_pdfs/
2. Get markdown from stage3_document_processed/{document}/{document}.md
3. Get extracted files from stage3_document_processed/{document}/
4. Create unified folder structure
```

#### Output Structure:

```
output/stage4_ready/
│
├── research_paper/
│   ├── research_paper.pdf           # ⭐ Normalized PDF (from Stage 1)
│   ├── research_paper.md            # ⭐ Docling markdown (from Stage 3)
│   └── docling_additional/
│       ├── metadata.json            # Spatial info, stats
│       ├── table_000.csv
│       ├── table_000.md
│       ├── image_001.png
│       └── image_002.png
│
├── presentation/
│   ├── presentation.pdf             # ⭐ Normalized PDF (from Stage 1)
│   ├── presentation.md              # ⭐ Docling markdown (from Stage 3)
│   └── docling_additional/
│       ├── metadata.json
│       └── image_001.png
│
├── lecture_video/
│   ├── lecture_video.md             # ⭐ NO PDF (video source)
│   └── docling_additional/
│       └── metadata.json
│
├── notes/                           # Original markdown file
│   ├── notes.md                     # ⭐ Docling-processed markdown
│   └── docling_additional/
│       └── metadata.json
│
└── data/                            # CSV file
    ├── data.md                      # ⭐ Markdown representation
    └── docling_additional/
        ├── metadata.json
        └── table_000.csv
```

#### Consolidation Rules:

| File Type | Has Normalized PDF? | Stage 4 Structure |
|-----------|---------------------|-------------------|
| PDF (original) | ✅ Yes (copy) | `file.pdf` + `file.md` |
| DOCX/PPTX/XLSX | ✅ Yes (converted) | `file.pdf` + `file.md` |
| HTML/Images | ✅ Yes (converted) | `file.pdf` + `file.md` |
| Video/Audio | ❌ No | `file.md` only |
| Markdown/TXT | ❌ No | `file.md` only |
| CSV | ❌ No | `file.md` only |
| AsciiDoc | ❌ No | `file.md` only |
| WebVTT | ❌ No | `file.md` only |

---

## 🔧 IMPLEMENTATION CHANGES

### **1. Stage 1: `normalizer.py` Modifications**

**File**: `src/normalizer.py`

#### Changes Required:

```python
# ❌ REMOVE: These markdown conversion methods
def _docx_to_markdown(self, doc: 'Document') -> str:  # DELETE
def _pptx_to_markdown(self, prs: 'Presentation') -> str:  # DELETE
def _html_to_markdown(self, soup: BeautifulSoup) -> str:  # DELETE
def _excel_to_markdown(self, df) -> str:  # DELETE
def _csv_to_markdown(self, df: pd.DataFrame) -> str:  # DELETE

# ❌ REMOVE: Calls to _save_markdown() in normalization methods

# ✅ KEEP: PDF conversion methods
def _docx_to_pdf_libreoffice(...)  # KEEP
def _pptx_to_pdf(...)  # KEEP
def _html_to_pdf(...)  # KEEP

# ✅ ADD: Support for new formats
def _copy_asciidoc(self, file_path: Path, stem: str):
    """Copy AsciiDoc files to original_files for Docling."""
    dest = self.originals_dir / file_path.name
    shutil.copy(file_path, dest)

def _copy_webvtt(self, file_path: Path, stem: str):
    """Copy WebVTT files to original_files for Docling."""
    dest = self.originals_dir / file_path.name
    shutil.copy(file_path, dest)

# ✅ MODIFY: _normalize_file() to handle new formats
def _normalize_file(self, file_path: Path):
    ext = file_path.suffix.lower()
    stem = file_path.stem
    safe_stem = self._get_safe_filename(stem)
    
    # Copy ALL files except media to original_files for Stage 3
    if ext not in ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.aac', '.ogg', '.flac']:
        original_copy = self.originals_dir / f"{safe_stem}{ext}"
        shutil.copy2(file_path, original_copy)
    
    # Only convert to PDF for specific formats
    if ext in ['.docx', '.pptx', '.xlsx', '.html', '.htm', '.xhtml']:
        # Convert to PDF for image-based RAG
        self._convert_to_pdf(file_path, safe_stem)
    elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp']:
        # Convert images to PDF
        self._image_to_pdf(file_path, safe_stem)
    elif ext == '.txt':
        # Convert TXT to MD
        self._txt_to_md(file_path, safe_stem)
    elif ext == '.md':
        # Copy markdown as-is
        self._copy_text(file_path, safe_stem)
    elif ext == '.pdf':
        # Copy PDF to both locations
        self._copy_pdf(file_path, safe_stem)
    # CSV, AsciiDoc, WebVTT - already copied to original_files, no further action
```

#### New Methods:

```python
def _txt_to_md(self, file_path: Path, stem: str):
    """Convert TXT to MD format."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    md_path = self.markdown_dir / f"{stem}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Converted TXT to MD: {md_path}")
```

---

### **2. Stage 2: `media_processor.py` Modifications**

**File**: `src/media_processor.py`

#### Changes Required:

```python
# ✅ ADD: Export transcript as markdown
def _save_transcript(self, stem: str, transcript: Dict) -> Dict[str, Path]:
    """
    Save transcript in multiple formats including markdown.
    """
    paths = {}
    
    # Plain text (keep existing)
    if self.config.export_txt:
        txt_path = self.transcript_dir / f"{stem}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(transcript.get('text', ''))
        paths['txt'] = txt_path
    
    # ⭐ NEW: Markdown format for Docling processing
    md_path = self.transcript_dir / f"{stem}.md"
    markdown_content = self._transcript_to_markdown(transcript)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    paths['md'] = md_path
    
    # JSON, SRT, VTT (keep existing)
    # ... existing code ...
    
    return paths

# ⭐ NEW METHOD
def _transcript_to_markdown(self, transcript: Dict) -> str:
    """
    Convert transcript to structured markdown format.
    
    Format:
    # Transcript: {filename}
    
    **Duration**: {duration}
    **Language**: {language}
    
    ## Transcript Content
    
    [00:00:00] Text segment 1...
    [00:00:05] Text segment 2...
    """
    lines = []
    
    # Header
    lines.append(f"# Transcript\n")
    lines.append(f"**Duration**: {transcript.get('duration', 'N/A')}")
    lines.append(f"**Language**: {transcript.get('language', 'auto')}\n")
    lines.append("## Transcript Content\n")
    
    # Add segments with timestamps
    if 'segments' in transcript:
        for segment in transcript['segments']:
            timestamp = self._format_timestamp_readable(segment['start'])
            text = segment['text'].strip()
            lines.append(f"**[{timestamp}]** {text}\n")
    else:
        # Fallback to plain text
        lines.append(transcript.get('text', ''))
    
    return '\n'.join(lines)

def _format_timestamp_readable(self, seconds: float) -> str:
    """Format seconds as readable timestamp [HH:MM:SS]."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
```

#### Config Update:

```python
@dataclass
class MediaProcessorConfig:
    # ... existing fields ...
    
    # ⭐ ADD: Always export markdown for Stage 3
    export_markdown: bool = True  # NEW: Always True
```

---

### **3. Stage 3: `document_processor.py` Modifications**

**File**: `src/document_processor.py`

#### Changes Required:

```python
class MultimodalDocumentProcessor:
    # ✅ UPDATE: Supported formats
    DOCLING_SUPPORTED_FORMATS = {
        'pdf': ['.pdf'],
        'office': ['.docx', '.pptx', '.xlsx'],
        'image': ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'],  # ADD .webp
        'web': ['.html', '.htm', '.xhtml'],  # ADD .xhtml
        'text': ['.md', '.txt'],
        'csv': ['.csv'],  # ⭐ ADD
        'asciidoc': ['.adoc', '.asciidoc', '.asc'],  # ⭐ ADD
        'webvtt': ['.vtt']  # ⭐ ADD
    }
    
    # ❌ REMOVE: CONVERTIBLE_FORMATS (no longer needed)
    
    def _initialize_converters(self) -> None:
        """Initialize Docling converters with format support."""
        # Existing code for PDF/Image formats...
        
        # ⭐ ADD: Format options for new formats if needed
        # Most formats use default Docling processing, which is fine
        pass
    
    def scan_input_directory(self) -> List[Path]:
        """Scan for all supported files."""
        supported_files = []
        
        for category, extensions in self.DOCLING_SUPPORTED_FORMATS.items():
            for ext in extensions:
                supported_files.extend(self.input_dir.rglob(f"*{ext}"))
        
        # ⭐ FILTER: Skip non-markdown transcript files
        filtered_files = []
        for file in supported_files:
            # Skip .json, .srt, .vtt files from transcripts directory
            if file.parent.name == 'transcripts' and file.suffix in ['.json', '.srt', '.vtt', '.txt']:
                logger.info(f"Skipping transcript file: {file.name}")
                continue
            filtered_files.append(file)
        
        return sorted(filtered_files)
```

---

### **4. Stage 3: `pipeline.py` Modifications**

**File**: `pipeline.py`

#### Changes Required:

```python
def _run_document_processing(self) -> Dict:
    """
    Run Stage 3: Document Processing with Docling.
    
    Process ALL files through Docling:
    - Original files (best quality)
    - Normalized PDFs (for better OCR)
    - Original markdown files
    - Video transcript markdown files
    """
    print("Processing documents with Docling...")
    print("Note: Processing ALL files for comprehensive extraction")
    
    try:
        inputs_to_process = []
        
        # 1. Process ORIGINAL files (full quality)
        originals_dir = self.stage_dirs["normalized"] / "original_files"
        if originals_dir.exists() and any(originals_dir.iterdir()):
            print(f"  → Adding ORIGINAL files: {originals_dir}")
            inputs_to_process.append(originals_dir)
        
        # 2. Process NORMALIZED PDFs (for better OCR on converted files)
        normalized_pdfs_dir = self.stage_dirs["normalized"] / "normalized_pdfs"
        if normalized_pdfs_dir.exists() and any(normalized_pdfs_dir.iterdir()):
            print(f"  → Adding NORMALIZED PDFs: {normalized_pdfs_dir}")
            inputs_to_process.append(normalized_pdfs_dir)
        
        # 3. Process ORIGINAL MARKDOWN files (TXT→MD conversions)
        normalized_md_dir = self.stage_dirs["normalized"] / "normalized_markdown"
        if normalized_md_dir.exists() and any(normalized_md_dir.iterdir()):
            print(f"  → Adding MARKDOWN files: {normalized_md_dir}")
            inputs_to_process.append(normalized_md_dir)
        
        # 4. Process VIDEO TRANSCRIPT markdown files
        transcript_md_files = []
        transcript_dir = self.stage_dirs["media_processed"] / "transcripts"
        if transcript_dir.exists():
            transcript_md_files = list(transcript_dir.glob("*.md"))
            if transcript_md_files:
                print(f"  → Adding TRANSCRIPT markdown files: {len(transcript_md_files)} files")
                # Create temporary directory for transcripts
                temp_transcript_dir = self.stage_dirs["media_processed"] / "transcripts_md_only"
                temp_transcript_dir.mkdir(exist_ok=True)
                
                # Copy only .md files
                for md_file in transcript_md_files:
                    shutil.copy(md_file, temp_transcript_dir / md_file.name)
                
                inputs_to_process.append(temp_transcript_dir)
        
        if not inputs_to_process:
            print("WARNING: No inputs found for document processing")
            return {"processed_files": 0, "total_files": 0}
        
        # Process each input directory
        all_stats = {"processed_files": 0, "failed_files": 0, "total_files": 0}
        
        for input_path in inputs_to_process:
            print(f"Processing files from: {input_path}")
            
            processor = MultimodalDocumentProcessor(
                input_dir=input_path,
                output_dir=self.stage_dirs["final_processed"],
                config=self.config.document_config
            )
            
            stats = processor.process_batch()
            
            # Aggregate statistics
            all_stats["processed_files"] += stats.get("processed_files", 0)
            all_stats["failed_files"] += stats.get("failed_files", 0)
            all_stats["total_files"] += stats.get("total_files", 0)
        
        print(f"✓ Document processing complete: {all_stats['processed_files']}/{all_stats['total_files']} files")
        return all_stats
    
    except Exception as e:
        print(f"ERROR: ✗ Document processing failed: {str(e)}")
        raise
```

---

### **5. NEW Stage 4: `consolidator.py` (NEW FILE)**

**File**: `src/consolidator.py`

```python
"""
Stage 4 Consolidator

Consolidates processed files from Stage 1-3 into a unified RAG-ready structure.

Output Structure:
- file.pdf (optional - if normalized PDF exists)
- file.md (required - from Docling processing)
- docling_additional/ (extracted images, tables, metadata)
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
import json
from datetime import datetime
from tqdm import tqdm
from loguru import logger


@dataclass
class ConsolidatorConfig:
    """Configuration for Stage 4 consolidation."""
    include_normalized_pdfs: bool = True  # Include PDFs from Stage 1
    include_metadata: bool = True         # Include Docling metadata
    include_tables: bool = True           # Include extracted tables
    include_images: bool = True           # Include extracted images


class Stage4Consolidator:
    """
    Consolidates Stage 1-3 outputs into unified RAG-ready structure.
    """
    
    def __init__(
        self,
        stage1_dir: Union[str, Path],
        stage3_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[ConsolidatorConfig] = None
    ):
        self.stage1_dir = Path(stage1_dir)
        self.stage3_dir = Path(stage3_dir)
        self.output_dir = Path(output_dir)
        self.config = config or ConsolidatorConfig()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            'total_documents': 0,
            'with_pdf': 0,
            'without_pdf': 0,
            'errors': []
        }
    
    def consolidate(self) -> Dict:
        """
        Consolidate all processed documents into unified structure.
        """
        print("="*80)
        print("STAGE 4: RAG-READY CONSOLIDATION")
        print("="*80)
        
        # Find all document folders in Stage 3
        doc_folders = [d for d in self.stage3_dir.iterdir() if d.is_dir() and d.name != 'logs']
        
        self.stats['total_documents'] = len(doc_folders)
        print(f"Found {len(doc_folders)} documents to consolidate")
        
        # Process each document
        for doc_folder in tqdm(doc_folders, desc="Consolidating documents"):
            try:
                self._consolidate_document(doc_folder)
            except Exception as e:
                logger.error(f"Failed to consolidate {doc_folder.name}: {e}")
                self.stats['errors'].append({
                    'document': doc_folder.name,
                    'error': str(e)
                })
        
        # Save statistics
        self._save_stats()
        
        # Print summary
        self._print_summary()
        
        return self.stats
    
    def _consolidate_document(self, doc_folder: Path):
        """
        Consolidate a single document into RAG-ready structure.
        
        Args:
            doc_folder: Path to Stage 3 document folder
        """
        doc_name = doc_folder.name
        
        # Create output folder
        output_folder = self.output_dir / doc_name
        output_folder.mkdir(exist_ok=True)
        
        # 1. Copy main markdown file (REQUIRED)
        stage3_md = doc_folder / f"{doc_name}.md"
        if not stage3_md.exists():
            raise FileNotFoundError(f"Markdown file not found: {stage3_md}")
        
        output_md = output_folder / f"{doc_name}.md"
        shutil.copy2(stage3_md, output_md)
        logger.info(f"✓ Copied markdown: {output_md.name}")
        
        # 2. Copy normalized PDF if exists (OPTIONAL)
        pdf_copied = False
        if self.config.include_normalized_pdfs:
            normalized_pdfs_dir = self.stage1_dir / "normalized_pdfs"
            
            # Try exact match
            stage1_pdf = normalized_pdfs_dir / f"{doc_name}.pdf"
            if stage1_pdf.exists():
                output_pdf = output_folder / f"{doc_name}.pdf"
                shutil.copy2(stage1_pdf, output_pdf)
                logger.info(f"✓ Copied normalized PDF: {output_pdf.name}")
                pdf_copied = True
                self.stats['with_pdf'] += 1
        
        if not pdf_copied:
            self.stats['without_pdf'] += 1
        
        # 3. Create docling_additional/ subfolder
        additional_dir = output_folder / "docling_additional"
        additional_dir.mkdir(exist_ok=True)
        
        # 4. Copy metadata
        if self.config.include_metadata:
            stage3_metadata = doc_folder / f"{doc_name}_metadata.json"
            if stage3_metadata.exists():
                output_metadata = additional_dir / "metadata.json"
                shutil.copy2(stage3_metadata, output_metadata)
                logger.debug(f"  ✓ Copied metadata")
        
        # 5. Copy extracted tables
        if self.config.include_tables:
            for table_file in doc_folder.glob("table_*"):
                shutil.copy2(table_file, additional_dir / table_file.name)
                logger.debug(f"  ✓ Copied table: {table_file.name}")
        
        # 6. Copy extracted images
        if self.config.include_images:
            for image_file in doc_folder.glob("image_*"):
                shutil.copy2(image_file, additional_dir / image_file.name)
                logger.debug(f"  ✓ Copied image: {image_file.name}")
    
    def _save_stats(self):
        """Save consolidation statistics."""
        stats_file = self.output_dir / "consolidation_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Statistics saved to: {stats_file}")
    
    def _print_summary(self):
        """Print consolidation summary."""
        print("\n" + "="*80)
        print("CONSOLIDATION SUMMARY")
        print("="*80)
        print(f"Total documents: {self.stats['total_documents']}")
        print(f"  With PDF: {self.stats['with_pdf']}")
        print(f"  Without PDF: {self.stats['without_pdf']}")
        
        if self.stats['errors']:
            print(f"\nErrors: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error['document']}: {error['error']}")
        
        print("="*80)
```

---

### **6. Update `pipeline.py` to include Stage 4**

**File**: `pipeline.py`

```python
# Add import
from src.consolidator import Stage4Consolidator, ConsolidatorConfig

class DocumentProcessingPipeline:
    def __init__(self, ...):
        # ... existing code ...
        
        # Add Stage 4 directory
        self.stage_dirs = {
            "raw": self.input_dir,
            "normalized": self.output_dir / "stage1_normalized",
            "media_processed": self.output_dir / "stage2_media_processed",
            "final_processed": self.output_dir / "stage3_document_processed",
            "rag_ready": self.output_dir / "stage4_ready"  # ⭐ NEW
        }
    
    def run(self) -> Dict:
        """Run the complete processing pipeline."""
        # ... existing Stage 1-3 code ...
        
        # Stage 4: Consolidation
        if self.config.enable_document_processing:  # Run after Stage 3
            print("\n" + "="*80)
            print("STAGE 4: RAG-READY CONSOLIDATION")
            print("="*80)
            consolidation_stats = self._run_consolidation()
            self.pipeline_stats["stages"]["consolidation"] = consolidation_stats
        
        # ... rest of code ...
    
    def _run_consolidation(self) -> Dict:
        """
        Run Stage 4: Consolidate outputs into RAG-ready structure.
        """
        print("Consolidating processed files into unified structure...")
        
        try:
            consolidator = Stage4Consolidator(
                stage1_dir=self.stage_dirs["normalized"],
                stage3_dir=self.stage_dirs["final_processed"],
                output_dir=self.stage_dirs["rag_ready"],
                config=ConsolidatorConfig()
            )
            
            stats = consolidator.consolidate()
            
            print(f"✓ Consolidation complete: {stats['total_documents']} documents")
            return stats
        
        except Exception as e:
            print(f"ERROR: ✗ Consolidation failed: {str(e)}")
            raise
```

---

## 📊 EXPECTED FINAL OUTPUT

After running the complete pipeline:

```
output/
│
├── stage1_normalized/
│   ├── normalized_pdfs/          # PDFs for image-based RAG
│   ├── original_files/           # Original files for Docling
│   ├── normalized_markdown/      # TXT→MD conversions
│   └── normalization_metadata/
│
├── stage2_media_processed/
│   ├── extracted_audio/
│   ├── transcripts/              # Includes .md files
│   ├── extracted_frames/
│   └── media_metadata/
│
├── stage3_document_processed/
│   ├── document1/                # Docling outputs
│   ├── document2/
│   └── logs/
│
└── stage4_ready/                 # ⭐ RAG-READY OUTPUT
    ├── research_paper/
    │   ├── research_paper.pdf
    │   ├── research_paper.md
    │   └── docling_additional/
    │
    ├── presentation/
    │   ├── presentation.pdf
    │   ├── presentation.md
    │   └── docling_additional/
    │
    ├── lecture_video/
    │   ├── lecture_video.md      # No PDF (video source)
    │   └── docling_additional/
    │
    └── consolidation_stats.json
```

---

## 🚀 IMPLEMENTATION SEQUENCE

### Phase 1: Foundation (Do First)
1. ✅ Create `src/consolidator.py` (new file)
2. ✅ Update `src/normalizer.py`:
   - Remove markdown conversion methods
   - Add AsciiDoc/WebVTT support
   - Modify `_normalize_file()` logic
3. ✅ Update `src/media_processor.py`:
   - Add `_transcript_to_markdown()` method
   - Update `_save_transcript()` to export `.md`

### Phase 2: Core Processing
4. ✅ Update `src/document_processor.py`:
   - Add new format support (CSV, AsciiDoc, WebVTT, WEBP, XHTML)
   - Update `scan_input_directory()` to filter transcript files
5. ✅ Update `pipeline.py`:
   - Modify `_run_document_processing()` to include all sources
   - Add `_run_consolidation()` method
   - Update stage directories

### Phase 3: Testing
6. ✅ Test Stage 1 with sample files
7. ✅ Test Stage 2 with video/audio
8. ✅ Test Stage 3 with all format types
9. ✅ Test Stage 4 consolidation
10. ✅ Verify final output structure

---

## ✅ VALIDATION CHECKLIST

After implementation, verify:

- [ ] Stage 1 only creates PDFs (no markdown except TXT→MD)
- [ ] Stage 1 preserves all original files in `original_files/`
- [ ] Stage 2 generates `.md` files for transcripts
- [ ] Stage 3 processes all files from Stage 1 & 2
- [ ] Stage 3 supports: PDF, DOCX, XLSX, PPTX, MD, HTML, XHTML, CSV, Images, AsciiDoc, WebVTT
- [ ] Stage 3 filters out non-MD transcript files (.json, .srt, .vtt, .txt)
- [ ] Stage 4 creates unified structure with:
  - [ ] `file.pdf` (when available)
  - [ ] `file.md` (always present)
  - [ ] `docling_additional/` subfolder
- [ ] No duplicate processing
- [ ] All files ready for RAG chunking and embedding

---

## 📝 NOTES

1. **Backward Compatibility**: This is a breaking change. Existing output folders should be backed up.

2. **Performance**: Stage 3 will process more files (both originals and normalized PDFs). Consider processing time.

3. **Storage**: Stage 4 consolidation will create some duplication (markdown from Stage 3, PDFs from Stage 1).

4. **Testing**: Test with diverse file types to ensure all formats work correctly.

5. **Future Enhancement**: Consider parallel processing for Stage 3 if processing time is too long.

---

**Ready to implement?** Follow the implementation sequence above, starting with Phase 1.
