# Stage 3: Document Processing with Docling - Detailed Documentation

## Table of Contents
1. [Overview](#overview)
2. [Module: document_processor.py](#module-document_processorpy)
3. [Docling Integration](#docling-integration)
4. [Processing Workflows](#processing-workflows)
5. [Function Reference](#function-reference)
6. [Advanced Features](#advanced-features)
7. [Examples](#examples)

---

## Overview

**Stage 3: Document Processing** performs deep document analysis using IBM Research's Docling library, enabling advanced OCR, Visual Language Model (VLM) integration, table extraction, and structured output generation.

### Purpose
- **Deep Document Understanding**: Extract text, images, tables with layout preservation
- **OCR Processing**: Convert scanned PDFs and images to searchable text
- **Visual Language Models**: Generate descriptions for images and diagrams
- **Structured Export**: Markdown, images, tables, metadata for RAG systems

### Why Process Originals (Not Stage 1 PDFs)?
- **Better Quality**: Original DOCX/PPTX files retain formatting
- **Image Preservation**: Embedded images are clearer in originals
- **Layout Understanding**: Docling better understands original formats
- **Dual Output**: Stage 1 PDFs for image RAG, Stage 3 Markdown for text RAG

---

## Module: document_processor.py

### Key Classes

#### 1. `ProcessingConfig`
Configuration dataclass for Docling processing behavior.

**Attributes**:
```python
@dataclass
class ProcessingConfig:
    # General settings
    use_gpu: bool = True                    # GPU acceleration
    enable_ocr: bool = True                 # Enable OCR
    enable_vlm: bool = True                 # Enable VLM for image descriptions
    enable_asr: bool = True                 # Enable ASR for audio (if applicable)
    
    # OCR settings
    ocr_engine: str = "rapidocr"            # rapidocr/tesseract/easyocr
    ocr_languages: List[str] = ["eng"]      # OCR languages
    
    # VLM settings
    vlm_model: str = "granite_docling"      # VLM model for image understanding
    
    # ASR settings
    asr_model: str = "whisper"              # ASR model
    
    # Export settings
    export_markdown: bool = True            # Export to Markdown
    export_images: bool = True              # Extract images
    export_tables: bool = True              # Extract tables (CSV + MD)
    export_metadata: bool = True            # Save processing metadata
    
    # Image filtering (FILTER OUT SMALL ICONS)
    min_image_width: int = 100              # Minimum width in pixels
    min_image_height: int = 100             # Minimum height in pixels
    min_image_area: int = 10000             # Minimum total area (100x100)
    
    # Output organization
    create_subfolder_per_doc: bool = True   # Create subfolder for each doc
    preserve_structure: bool = True         # Preserve directory structure
```

#### 2. `MultimodalDocumentProcessor`
Main Docling orchestrator for document processing.

**Initialization**:
```python
def __init__(
    self,
    input_dir: Union[str, Path],           # Original files directory
    output_dir: Union[str, Path],          # Output directory
    config: Optional[ProcessingConfig] = None
):
```

**Supported Formats**:
```python
DOCLING_SUPPORTED_FORMATS = {
    'pdf': ['.pdf'],
    'office': ['.docx', '.pptx', '.xlsx'],
    'image': ['.png', '.jpg', '.jpeg', '.tiff', '.bmp'],
    'web': ['.html', '.htm'],
    'text': ['.md', '.txt']
}
```

---

## Docling Integration

### What is Docling?

**Docling** is IBM Research's advanced document understanding library that provides:
- **Layout Analysis**: Detects sections, headings, paragraphs, lists
- **OCR Engines**: RapidOCR, Tesseract, EasyOCR support
- **Visual Language Models**: Image and diagram understanding
- **Table Extraction**: Preserves table structure
- **Multimodal Processing**: Handles text, images, audio

### Pipeline Architecture

**Docling Processing Pipeline**:
```
Original File (DOCX/PDF/Image)
  │
  ├→ Format Detection
  │   └→ InputFormat enum (PDF, DOCX, PPTX, IMAGE, HTML, MD)
  │
  ├→ Backend Selection
  │   ├→ DoclingParseBackend (advanced, v4)
  │   └→ PyPdfiumBackend (fallback)
  │
  ├→ Pipeline Selection
  │   ├→ StandardPdfPipeline (PDF, Images)
  │   └→ SimplePipeline (Office docs, HTML, MD)
  │
  ├→ Processing Stages
  │   ├→ Layout Analysis (detect sections, headings)
  │   ├→ OCR (if enabled) → Extract text from images
  │   ├→ Table Detection → Extract table structure
  │   ├→ Image Extraction → Save embedded images
  │   └→ VLM (if enabled) → Generate image descriptions
  │
  └→ DoclingDocument Object
      ├→ Markdown representation
      ├→ Extracted images
      ├→ Extracted tables
      └→ Metadata (pages, structure, statistics)
```

### Enhanced Pipeline Options

**PDF/Image Advanced Processing**:
```python
PdfPipelineOptions(
    do_ocr=True,                          # Enable OCR
    do_table_structure=True,              # Extract tables
    generate_picture_images=True,         # CRITICAL: Extract images
    generate_page_images=True,            # Full page images
    generate_table_images=True,           # Table images
    do_picture_classification=True,       # Classify images
    do_picture_description=True,          # VLM descriptions
    images_scale=2.0,                     # 2x resolution for quality
    ocr_options=RapidOcrOptions(...),     # OCR config
    picture_description_options=VlmOptions(...)  # VLM config
)
```

**Office/Web/Text Default Processing**:
```python
# Docling automatically handles these formats with optimized settings
# No custom pipeline needed - uses SimplePipeline internally
```

---

## Processing Workflows

### Workflow 1: PDF → Markdown + Images + Tables

**Complete Pipeline**:
```
PDF File
  │
  ├→ Stage 1: Document Loading
  │   ├→ Detect format: InputFormat.PDF
  │   ├→ Load with DoclingParseBackend
  │   └→ Initialize StandardPdfPipeline
  │
  ├→ Stage 2: Layout Analysis
  │   ├→ Detect pages, sections, headings
  │   ├→ Identify text blocks, paragraphs
  │   ├→ Locate images, diagrams, figures
  │   └→ Find tables and their structure
  │
  ├→ Stage 3: Content Extraction
  │   ├→ OCR (if scanned): Extract text from images
  │   ├→ Text: Extract all text with formatting
  │   ├→ Images: Extract with 2x resolution
  │   └→ Tables: Extract structure + data
  │
  ├→ Stage 4: VLM Processing (Optional)
  │   ├→ Detect images > 100x100px
  │   ├→ Generate descriptions with SmolVLM
  │   └→ Add descriptions to markdown
  │
  └→ Stage 5: Export
      ├→ Markdown: Structured text
      ├→ Images: Filtered (>100x100px)
      ├→ Tables: CSV + Markdown format
      └→ Metadata: JSON with statistics
```

**Example Output**:
```
Input:  research_paper.pdf (50 pages, 10 images, 5 tables)
Output:
  research_paper/
    ├── research_paper.md              # Main markdown
    ├── research_paper_metadata.json   # Statistics
    ├── images/
    │   ├── image_001.png             # Extracted images (filtered)
    │   ├── image_002.png
    │   └── image_005.png             # (10 images, 5 kept after filtering)
    └── tables/
        ├── table_000.csv             # Table data
        ├── table_000.md              # Table markdown
        ├── table_001.csv
        └── table_001.md
```

### Workflow 2: DOCX → Markdown + Images + Tables

**Process**:
```
DOCX File (Original from Stage 1)
  │
  ├→ Docling SimplePipeline
  │   ├→ Parse DOCX structure (python-docx internally)
  │   ├→ Extract headings, paragraphs, lists
  │   ├→ Extract embedded images
  │   └→ Extract tables with formatting
  │
  ├→ Content Processing
  │   ├→ Preserve heading hierarchy (# ## ###)
  │   ├→ Extract images (better quality than Stage 1 PDF)
  │   └→ Convert tables to markdown
  │
  └→ Export
      ├→ Markdown with structure
      ├→ High-quality embedded images
      └→ Table data (CSV + MD)
```

**Why Process Original DOCX?**
- Better image quality (no PDF compression)
- Preserves formatting and styles
- Faster processing (no OCR needed)
- Direct access to embedded content

### Workflow 3: Image → Markdown (OCR + VLM)

**Process**:
```
Image File (PNG/JPG)
  │
  ├→ Detect Format: InputFormat.IMAGE
  │
  ├→ StandardPdfPipeline (same as PDF)
  │   ├→ OCR: Extract text from image
  │   ├→ Layout: Detect structure
  │   └→ VLM: Generate image description
  │
  └→ Export
      ├→ Markdown: OCR text + VLM description
      ├→ Original image (copied)
      └→ Metadata
```

**Example**:
```markdown
# Image: screenshot.png

## Visual Description
A screenshot showing a Python code snippet for data processing with pandas.

## Extracted Text (OCR)
import pandas as pd
df = pd.read_csv('data.csv')
print(df.head())
```

### Workflow 4: Transcribed Text → Markdown

**Process**:
```
Transcript Text (from Stage 2)
  │
  ├→ Convert TXT to Markdown
  │   ├→ Add title: # {filename}
  │   └→ Format content
  │
  ├→ Process with Docling
  │   └→ SimplePipeline for markdown
  │
  └→ Export
      └→ Normalized markdown
```

---

## Function Reference

### Main Processing Functions

#### `process_batch() -> Dict`
Process all files in input directory.

**Returns**:
```python
{
    "total_files": 25,
    "processed_files": 23,
    "failed_files": 2,
    "processing_time": 120.5,
    "file_types": {
        "pdf": 10,
        "office": 8,
        "image": 5,
        "text": 2
    },
    "errors": [...]
}
```

**Usage**:
```python
processor = MultimodalDocumentProcessor(
    input_dir="./stage1_normalized/original_files",
    output_dir="./output/stage3"
)
stats = processor.process_batch()
```

#### `process_single_file(file_path: Path) -> Dict`
Process a single file with Docling.

**Returns**:
```python
{
    'file_path': str,
    'file_size': int,
    'file_type': str,
    'processing_time': float,
    'pages': int,
    'success': bool,
    'doc_object': DoclingDocument,    # Docling document object
    'result_object': ConversionResult, # Conversion result
    'error': None or str
}
```

**Process**:
1. Detect file format
2. Convert TXT to MD if needed (temporary file)
3. Run Docling converter
4. Extract DoclingDocument object
5. Return processing info

**Example**:
```python
result = processor.process_single_file(Path("document.pdf"))
if result['success']:
    doc = result['doc_object']
    print(f"Pages: {result['pages']}")
    print(f"Processing time: {result['processing_time']}s")
```

### Export Functions

#### `_export_markdown(doc, output_path, file_path)`
Export document to Markdown format.

**Process**:
1. Get markdown from DoclingDocument
2. Clean up formatting
3. Add VLM image descriptions (if enabled)
4. Save to file

**Output**: `{filename}.md`

**Example Markdown**:
```markdown
# Research Paper Title

## Abstract
This paper presents...

## Introduction
Recent advances in AI...

![Figure 1](images/image_001.png)
*Figure 1: System architecture diagram*

| Method | Accuracy | Speed |
|--------|----------|-------|
| A      | 95%      | Fast  |
| B      | 92%      | Slow  |
```

#### `_export_images(doc, output_subdir, file_stem)`
Export extracted images with filtering.

**Image Filtering Logic**:
```python
def _should_keep_image(image) -> bool:
    width, height = image.size
    area = width * height
    
    # Filter conditions
    if width < min_image_width:        # Skip small width
        return False
    if height < min_image_height:      # Skip small height
        return False
    if area < min_image_area:          # Skip small total area
        return False
    
    return True  # Keep image
```

**Why Filter Images?**
- Remove small icons (<100x100px)
- Remove decorative elements
- Keep only meaningful images
- Reduce storage and noise in RAG

**Output**:
```
images/
├── image_001.png    # Kept: 500x400px (200,000 area)
├── image_002.png    # Kept: 300x300px (90,000 area)
└── (icon_small.png skipped: 50x50px = 2,500 area < 10,000)
```

#### `_export_tables(doc, output_subdir)`
Export tables in CSV and Markdown formats.

**Process**:
1. Iterate through tables in DoclingDocument
2. Convert each table to Pandas DataFrame
3. Save as CSV (machine-readable)
4. Save as Markdown (human-readable)

**Output**:
```
tables/
├── table_000.csv      # CSV format
├── table_000.md       # Markdown format
├── table_001.csv
└── table_001.md
```

**CSV Example**:
```csv
Method,Accuracy,Speed
Method A,95%,Fast
Method B,92%,Slow
```

**Markdown Example**:
```markdown
| Method   | Accuracy | Speed |
|----------|----------|-------|
| Method A | 95%      | Fast  |
| Method B | 92%      | Slow  |
```

#### `_export_metadata(processing_info, output_path)`
Save processing metadata as JSON.

**Metadata Structure**:
```json
{
  "source_file": "research_paper.pdf",
  "processing_date": "2025-11-21T10:30:00",
  "docling_version": "1.x",
  "file_size": 5242880,
  "file_type": "pdf",
  "processing_time": 12.5,
  "statistics": {
    "pages": 50,
    "images_found": 10,
    "images_exported": 5,
    "tables": 3,
    "total_text_length": 25000
  }
}
```

### Initialization Functions

#### `_initialize_converters()`
Initialize Docling converter with enhanced format options.

**Process**:
1. Configure PDF/Image advanced pipeline
   - Enable OCR, VLM, table extraction
   - Set image scale to 2.0 (high resolution)
   - Configure picture description options
2. Let Docling handle other formats with defaults
3. Fallback to basic converter if configuration fails

**Format Options**:
```python
format_options = {
    InputFormat.PDF: FormatOption(
        pipeline_cls=StandardPdfPipeline,
        backend=DoclingParseBackend,
        pipeline_options=pdf_options
    ),
    InputFormat.IMAGE: FormatOption(
        pipeline_cls=StandardPdfPipeline,
        backend=DoclingParseBackend,
        pipeline_options=pdf_options
    )
    # Other formats use Docling defaults
}
```

#### `_get_ocr_options() -> OcrOptions`
Configure OCR engine based on settings.

**Supported Engines**:
1. **RapidOCR** (Default, recommended)
   - Fast and accurate
   - Multi-language support
   - No external dependencies

2. **Tesseract**
   - Traditional OCR engine
   - Requires Tesseract installation
   - Good for English documents

3. **EasyOCR**
   - Deep learning-based
   - GPU acceleration
   - Requires language code mapping

**Configuration**:
```python
if ocr_engine == "rapidocr":
    return RapidOcrOptions(lang=["eng"])
elif ocr_engine == "tesseract":
    return TesseractOcrOptions(lang=["eng"])
elif ocr_engine == "easyocr":
    return EasyOcrOptions(lang=["en"], use_gpu=True)
```

#### `_get_vlm_options() -> PictureDescriptionVlmOptions`
Configure Visual Language Model for image understanding.

**Configuration**:
```python
VlmOptions(
    repo_id="HuggingFaceTB/SmolVLM-256M-Instruct",  # Model
    batch_size=8,                                    # Batch size
    scale=2,                                         # Image scale
    picture_area_threshold=0.0,                      # No area filter
    prompt="Describe this image in a few concise sentences.",
    generation_config={
        "max_new_tokens": 200,
        "do_sample": False
    }
)
```

**Why SmolVLM?**
- Lightweight (256M parameters)
- Fast inference
- Good quality descriptions
- Low VRAM requirements (2-4GB)

---

## Advanced Features

### 1. Image Filtering

**Problem**: Documents contain many small icons and decorative elements that add noise to RAG systems.

**Solution**: Filter images by size and area.

**Configuration**:
```python
config = ProcessingConfig(
    min_image_width=100,      # Minimum 100px wide
    min_image_height=100,     # Minimum 100px tall
    min_image_area=10000      # Minimum 10,000px² area
)
```

**Example**:
```
Input Document: 20 images
  - 5 small icons (32x32) → FILTERED OUT
  - 3 decorative elements (50x50) → FILTERED OUT
  - 2 logos (80x80) → FILTERED OUT
  - 10 meaningful images (>100x100) → KEPT

Output: 10 images (50% reduction)
```

### 2. GPU Acceleration

**Supported Operations**:
- OCR (EasyOCR)
- VLM (SmolVLM)
- Image processing

**Configuration**:
```python
config = ProcessingConfig(
    use_gpu=True,
    ocr_engine="easyocr",     # GPU-accelerated
    enable_vlm=True           # GPU-accelerated
)
```

**Performance**:
- **CPU**: 50 pages/minute
- **GPU**: 200 pages/minute (4x faster)

### 3. Multi-Language OCR

**Supported Languages** (RapidOCR):
- English (`eng`)
- Chinese Simplified (`chi_sim`)
- Japanese (`jpn`)
- Korean (`kor`)
- French (`fra`)
- German (`deu`)
- Spanish (`spa`)
- And more...

**Configuration**:
```python
config = ProcessingConfig(
    ocr_languages=["eng", "chi_sim"]  # English + Chinese
)
```

### 4. Table Structure Preservation

**Features**:
- Detects table headers
- Preserves row/column structure
- Exports to CSV (machine-readable)
- Exports to Markdown (human-readable)

**Example**:
```
Input: Complex table in PDF with merged cells
Output:
  - table_000.csv: Clean tabular data
  - table_000.md: Formatted markdown table
```

---

## Configuration Examples

### Production Configuration (Default)
```python
config = ProcessingConfig(
    use_gpu=True,
    enable_ocr=True,
    enable_vlm=True,
    ocr_engine="rapidocr",
    export_markdown=True,
    export_images=True,
    export_tables=True,
    min_image_width=100,
    min_image_height=100
)
```

### Fast Configuration (CPU, No VLM)
```python
config = ProcessingConfig(
    use_gpu=False,
    enable_ocr=True,
    enable_vlm=False,           # Disable VLM for speed
    ocr_engine="rapidocr",
    export_markdown=True,
    export_images=False,        # Skip image export
    export_tables=True
)
```

### Maximum Quality (GPU, All Features)
```python
config = ProcessingConfig(
    use_gpu=True,
    enable_ocr=True,
    enable_vlm=True,
    ocr_engine="easyocr",       # Best OCR
    export_markdown=True,
    export_images=True,
    export_tables=True,
    min_image_width=50,         # Keep more images
    min_image_height=50
)
```

---

## Examples

### Example 1: Basic Usage
```python
from document_processor import MultimodalDocumentProcessor

processor = MultimodalDocumentProcessor(
    input_dir="./stage1_normalized/original_files",
    output_dir="./output/stage3"
)

stats = processor.process_batch()
print(f"Processed: {stats['processed_files']}/{stats['total_files']}")
```

### Example 2: Custom Configuration
```python
from document_processor import MultimodalDocumentProcessor, ProcessingConfig

config = ProcessingConfig(
    use_gpu=True,
    enable_vlm=True,
    ocr_engine="rapidocr",
    min_image_area=20000      # Stricter filtering
)

processor = MultimodalDocumentProcessor(
    input_dir="./documents",
    output_dir="./output",
    config=config
)

stats = processor.process_batch()
```

### Example 3: Single File Processing
```python
processor = MultimodalDocumentProcessor(
    input_dir="./input",
    output_dir="./output"
)

result = processor.process_single_file(Path("report.pdf"))

if result['success']:
    print(f"Pages: {result['pages']}")
    print(f"Time: {result['processing_time']}s")
    doc = result['doc_object']
    # Access DoclingDocument methods...
```

---

## Output Structure

### Directory Layout
```
output/stage3_document_processed/
├── document1/                        # Per-document folder
│   ├── document1.md                 # Main markdown
│   ├── document1_metadata.json      # Processing metadata
│   ├── images/                       # Extracted images (filtered)
│   │   ├── image_001.png
│   │   └── image_002.png
│   └── tables/                       # Extracted tables
│       ├── table_000.csv
│       ├── table_000.md
│       └── table_001.csv
└── logs/
    └── batch_summary_*.json
```

---

## Dependencies

```bash
# Core Docling
pip install docling[all]            # Full Docling installation

# Optional backends
pip install docling-parse           # Advanced parsing backend

# OCR engines
pip install rapidocr-onnxruntime    # RapidOCR (recommended)
pip install pytesseract             # Tesseract
pip install easyocr                 # EasyOCR (GPU)

# VLM
pip install transformers torch      # For SmolVLM

# Utilities
pip install Pillow pandas loguru
```

---

## Performance Tips

1. **Use GPU**: 4x faster for OCR and VLM
2. **Choose RapidOCR**: Fastest OCR engine
3. **Disable VLM for Speed**: If descriptions not needed
4. **Increase Image Filtering**: Reduce output size
5. **Process Original Files**: Better than re-processing Stage 1 PDFs

---

## Next Steps

- **Complete API**: See [API_REFERENCE.md](API_REFERENCE.md)
- **Pipeline Overview**: See [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md)
