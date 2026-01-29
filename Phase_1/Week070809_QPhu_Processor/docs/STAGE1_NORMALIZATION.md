# Stage 1: Document Normalization - Detailed Documentation

## Table of Contents
1. [Overview](#overview)
2. [Module: normalizer.py](#module-normalizerpy)
3. [Conversion Workflows](#conversion-workflows)
4. [Function Reference](#function-reference)
5. [Configuration Options](#configuration-options)
6. [Examples](#examples)

---

## Overview

**Stage 1: Normalization** converts diverse document formats into standardized PDF and Markdown formats to prepare them for downstream processing.

### Purpose
- **Create PDFs** for image-based RAG (preserves visual layout)
- **Generate Markdown** for text-based RAG (structured text)
- **Preserve originals** for Stage 3 Docling processing (best quality)

### Supported Input Formats

| **Category** | **Extensions** | **Output** |
|-------------|---------------|-----------|
| **Documents** | `.docx`, `.doc`, `.odt`, `.rtf` | PDF + Markdown |
| **Presentations** | `.pptx`, `.ppt`, `.odp` | PDF + Markdown |
| **Web** | `.html`, `.htm`, `.mhtml` | Markdown |
| **Spreadsheets** | `.xlsx`, `.xls` | Markdown (tables) |
| **CSV** | `.csv` | Markdown (tables) |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff` | PDF |
| **Already Normalized** | `.pdf`, `.md`, `.txt` | Copy as-is |

---

## Module: normalizer.py

### Key Classes

#### 1. `NormalizerConfig`
Configuration dataclass for normalization behavior.

**Attributes**:
```python
@dataclass
class NormalizerConfig:
    # Output format preferences
    generate_pdf: bool = True              # Create PDF for image-based RAG
    generate_markdown: bool = True         # Create Markdown for text-based RAG
    
    # Image handling
    image_to_pdf: bool = True              # Convert standalone images to PDF
    image_quality: int = 95                # JPEG quality (0-100)
    
    # Spreadsheet handling
    excel_to_markdown: bool = True         # Convert Excel to MD tables
    csv_to_markdown: bool = True           # Convert CSV to MD tables
    max_table_rows: int = 1000             # Max rows to include
    
    # HTML handling
    html_preserve_formatting: bool = True  # Keep some HTML formatting
    
    # Document handling
    docx_extract_images: bool = True       # Extract embedded images
    pptx_extract_images: bool = True       # Extract slide images
    
    # PDF generation settings
    pdf_page_size: str = "A4"              # A4 or letter
    pdf_margin: float = 0.75               # Margin in inches
    
    # Output organization
    organize_by_type: bool = True          # Organize by file type
```

#### 2. `DocumentNormalizer`
Main normalization engine that coordinates all conversions.

**Initialization**:
```python
def __init__(
    self,
    input_dir: Union[str, Path],      # Source documents directory
    output_dir: Union[str, Path],     # Output directory
    config: Optional[NormalizerConfig] = None  # Configuration
):
```

**Key Attributes**:
- `self.pdf_dir`: Output directory for PDF files
- `self.markdown_dir`: Output directory for Markdown files
- `self.originals_dir`: Copies of original files for Stage 3
- `self.metadata_dir`: Processing statistics and metadata
- `self.stats`: Tracking dictionary for processing statistics

---

## Conversion Workflows

### Workflow 1: DOCX → PDF + Markdown

**Process**:
```
DOCX File
  ├→ Extract Text & Formatting
  │   ├→ Detect headings (Heading 1, Heading 2, ...)
  │   ├→ Extract paragraphs
  │   └→ Extract tables
  │
  ├→ Convert to Markdown (python-docx)
  │   ├→ Headings: # ## ### based on style
  │   ├→ Paragraphs: Plain text
  │   └→ Tables: Markdown table format
  │
  ├→ Convert to PDF (LibreOffice or ReportLab)
  │   ├→ Preferred: LibreOffice (preserves images, layout)
  │   └→ Fallback: ReportLab (text-only, no images)
  │
  └→ Save Original Copy (for Docling Stage 3)
```

**Key Functions**:
- `_normalize_docx(file_path, stem)`: Main DOCX handler
- `_docx_to_markdown(doc)`: Extract text to Markdown
- `_docx_to_pdf_libreoffice(file_path, stem)`: LibreOffice conversion
- `_docx_to_pdf(doc, stem)`: ReportLab fallback conversion
- `_table_to_markdown(table)`: Convert DOCX tables to Markdown

**Example Output**:
```markdown
# Introduction

This is a sample document.

## Section 1

Content here.

| Column 1 | Column 2 |
| --- | --- |
| Data 1 | Data 2 |
```

### Workflow 2: PPTX → PDF + Markdown

**Process**:
```
PPTX File
  ├→ Extract Slides (python-pptx)
  │   ├→ Extract text from shapes
  │   ├→ Preserve slide order
  │   └→ Optional: Extract images
  │
  ├→ Convert to Markdown
  │   ├→ ## Slide N for each slide
  │   ├→ Extract all shape text
  │   └→ Separator: ---
  │
  ├→ Convert to PDF (LibreOffice or ReportLab)
  │   ├→ Preferred: LibreOffice (preserves slide layout)
  │   └→ Fallback: ReportLab (text-only slides)
  │
  └→ Save Original Copy
```

**Key Functions**:
- `_normalize_pptx(file_path, stem)`
- `_pptx_to_markdown(prs)`: Extract presentation to Markdown
- `_pptx_to_pdf(prs, stem)`: ReportLab conversion (fallback)

**Example Output**:
```markdown
## Slide 1

Title: Introduction to AI

Content: Overview of AI concepts

---

## Slide 2

Subtitle: Machine Learning Basics

Points:
- Supervised Learning
- Unsupervised Learning
```

### Workflow 3: HTML → Markdown

**Process**:
```
HTML File
  ├→ Parse HTML (BeautifulSoup)
  │   ├→ Remove <script> and <style> tags
  │   └→ Extract text content
  │
  ├→ Clean Text
  │   ├→ Remove extra whitespace
  │   ├→ Preserve line breaks
  │   └→ Clean up formatting
  │
  └→ Save as Markdown
```

**Key Functions**:
- `_normalize_html(file_path, stem)`

**Example**:
```html
<!-- Input HTML -->
<h1>Title</h1>
<p>Paragraph text</p>
```
```markdown
# Title

Paragraph text
```

### Workflow 4: Excel/CSV → Markdown Tables

**Process**:
```
Excel/CSV File
  ├→ Load with Pandas
  │   ├→ Read all sheets (Excel)
  │   └→ Load CSV as DataFrame
  │
  ├→ Convert to Markdown
  │   ├→ Use df.to_markdown()
  │   ├→ Add sheet headers (Excel)
  │   └→ Limit rows if > max_table_rows
  │
  └→ Save as Markdown
```

**Key Functions**:
- `_normalize_excel(file_path, stem)`: Excel handler
- `_normalize_csv(file_path, stem)`: CSV handler

**Example Output**:
```markdown
## Sheet: Products

| Product ID | Name | Price |
| --- | --- | --- |
| 1 | Widget | 9.99 |
| 2 | Gadget | 19.99 |

---
```

### Workflow 5: Images → PDF

**Process**:
```
Image File
  ├→ Load with PIL
  │   └→ Support: PNG, JPG, JPEG, BMP, TIFF
  │
  ├→ Convert to PDF (img2pdf)
  │   ├→ Preserve image resolution
  │   ├→ Apply image quality settings
  │   └→ Create single-page PDF
  │
  └→ Save Original Copy
```

**Key Functions**:
- `_normalize_image(file_path, stem)`

### Workflow 6: PDF/Markdown → Copy As-Is

**Process**:
```
PDF/MD/TXT File
  ├→ Copy to normalized directory
  ├→ Save original copy (PDF only)
  └→ No conversion needed
```

**Key Functions**:
- `_copy_pdf(file_path, stem)`
- `_copy_text(file_path, stem)`

---

## Function Reference

### Main Processing Functions

#### `normalize_batch() -> Dict`
Process all files in the input directory.

**Returns**:
```python
{
    "total_files": 25,
    "normalized_files": 23,
    "failed_files": 2,
    "by_type": {
        "document": 10,
        "presentation": 5,
        "image": 8,
        "spreadsheet": 2
    },
    "errors": [
        {"file": "broken.docx", "error": "Corrupted file"}
    ]
}
```

**Usage**:
```python
normalizer = DocumentNormalizer(
    input_dir="./input",
    output_dir="./output/stage1"
)
stats = normalizer.normalize_batch()
print(f"Processed {stats['normalized_files']} files")
```

#### `_normalize_file(file_path: Path)`
Normalize a single file based on its extension.

**Process**:
1. Detect file type from extension
2. Dispatch to appropriate handler
3. Save original copy (if needed)
4. Update statistics

### LibreOffice Integration

#### `_docx_to_pdf_libreoffice(file_path, stem) -> bool`
Convert DOCX/PPTX to PDF using LibreOffice (highest quality).

**Features**:
- Preserves images and embedded content
- Maintains layout and formatting
- Works on Windows, macOS, Linux

**Platform-Specific Paths**:
```python
# Windows
r"C:\Program Files\LibreOffice\program\soffice.exe"

# macOS
"/Applications/LibreOffice.app/Contents/MacOS/soffice"

# Linux
"/usr/bin/soffice"
```

**Command**:
```bash
soffice --headless --convert-to pdf --outdir <output_dir> <input_file>
```

**Returns**:
- `True`: Conversion successful
- `False`: LibreOffice not available or conversion failed

**Fallback**: If LibreOffice not found, uses ReportLab (text-only).

### Utility Functions

#### `_get_file_type(ext: str) -> str`
Categorize file type from extension.

**Mapping**:
```python
{
    '.docx': 'document',
    '.pptx': 'presentation',
    '.html': 'web',
    '.xlsx': 'spreadsheet',
    '.png': 'image',
    '.pdf': 'pdf',
    '.md': 'markdown'
}
```

#### `_get_safe_filename(stem: str, max_length: int = 50) -> str`
Truncate long filenames and add hash for uniqueness.

**Why**: Windows has 260-character path limit.

**Example**:
```python
# Long filename
"This_is_a_very_long_filename_that_exceeds_50_characters"

# Safe filename
"This_is_a_very_long_filename_that_ex_ce6c70c7"
```

#### `_save_markdown(stem: str, content: str)`
Save markdown content to normalized_markdown directory.

**Output Path**:
```
output/stage1_normalized/normalized_markdown/{stem}.md
```

#### `_save_statistics()`
Save processing statistics to JSON.

**Output Path**:
```
output/stage1_normalized/normalization_metadata/normalization_stats.json
```

---

## Configuration Options

### Production Configuration (Default)
```python
config = NormalizerConfig(
    generate_pdf=True,              # Create PDFs for image RAG
    generate_markdown=True,         # Create Markdown for text RAG
    image_quality=95,               # High quality images
    max_table_rows=1000,            # Include full tables
    docx_extract_images=True,       # Extract embedded images
    pptx_extract_images=True        # Extract slide images
)
```

### Fast Configuration (Skip PDF Generation)
```python
config = NormalizerConfig(
    generate_pdf=False,             # Skip PDF creation
    generate_markdown=True,         # Only Markdown
    excel_to_markdown=True,         # Convert spreadsheets
    csv_to_markdown=True            # Convert CSV
)
```

### Minimal Configuration (Small Tables)
```python
config = NormalizerConfig(
    generate_pdf=True,
    generate_markdown=True,
    max_table_rows=100,             # Limit table size
    image_quality=75                # Smaller file sizes
)
```

---

## Examples

### Example 1: Basic Usage
```python
from normalizer import DocumentNormalizer, NormalizerConfig

# Initialize
normalizer = DocumentNormalizer(
    input_dir="./raw_documents",
    output_dir="./output/stage1_normalized"
)

# Process all files
stats = normalizer.normalize_batch()

# Check results
print(f"Total files: {stats['total_files']}")
print(f"Normalized: {stats['normalized_files']}")
print(f"Failed: {stats['failed_files']}")
```

### Example 2: Custom Configuration
```python
from normalizer import DocumentNormalizer, NormalizerConfig

# Custom config
config = NormalizerConfig(
    generate_pdf=False,          # Skip PDFs
    generate_markdown=True,      # Only Markdown
    max_table_rows=500           # Limit table size
)

# Initialize with config
normalizer = DocumentNormalizer(
    input_dir="./documents",
    output_dir="./output",
    config=config
)

# Process
stats = normalizer.normalize_batch()
```

### Example 3: Check LibreOffice Availability
```python
from pathlib import Path
import sys

# Check LibreOffice path
if sys.platform == 'win32':
    soffice = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    if soffice.exists():
        print("✓ LibreOffice available")
    else:
        print("✗ LibreOffice not found, will use ReportLab fallback")
```

---

## Output Structure

### Directory Layout
```
output/stage1_normalized/
├── normalized_pdfs/              # PDFs for image-based RAG
│   ├── document1.pdf
│   ├── presentation1.pdf
│   └── image1.pdf
├── normalized_markdown/          # Markdown for text-based RAG
│   ├── document1.md
│   ├── presentation1.md
│   ├── spreadsheet1.md
│   └── webpage1.md
├── original_files/               # Originals for Stage 3 Docling
│   ├── document1.docx           # (Copied, not modified)
│   ├── presentation1.pptx
│   └── webpage1.html
└── normalization_metadata/
    └── normalization_stats.json  # Processing statistics
```

### Statistics File Format
```json
{
  "total_files": 25,
  "normalized_files": 23,
  "failed_files": 2,
  "by_type": {
    "document": 10,
    "presentation": 5,
    "web": 3,
    "spreadsheet": 2,
    "csv": 1,
    "image": 8,
    "pdf": 2,
    "markdown": 1
  },
  "errors": [
    {
      "file": "/path/to/broken.docx",
      "error": "File is corrupted"
    }
  ]
}
```

---

## Dependencies

### Required Libraries
```bash
# Document processing
pip install python-docx      # DOCX processing
pip install python-pptx      # PPTX processing
pip install pandas           # Excel/CSV processing
pip install beautifulsoup4   # HTML processing
pip install lxml             # HTML parsing

# PDF generation
pip install reportlab        # PDF creation fallback
pip install img2pdf          # Image to PDF conversion
pip install Pillow           # Image processing

# Utilities
pip install tqdm             # Progress bars
```

### Optional (Recommended)
```bash
# LibreOffice - Install separately from:
# https://www.libreoffice.org/download/
# Provides highest quality DOCX/PPTX → PDF conversion
```

---

## Error Handling

### Common Errors

#### 1. LibreOffice Not Found
**Error**: "LibreOffice not found in system"
**Solution**: Install LibreOffice or accept ReportLab fallback
**Impact**: PDFs will be text-only (no images)

#### 2. Corrupted Files
**Error**: "Error processing DOCX: Corrupted file"
**Solution**: Manual file repair or skip file
**Impact**: File skipped, logged in errors array

#### 3. Large Tables
**Warning**: "Sheet 'Data' has 5000 rows, truncating to 1000"
**Solution**: Increase `max_table_rows` in config
**Impact**: Only first 1000 rows exported

#### 4. Long Filenames
**Warning**: Filename truncated automatically
**Solution**: None needed (automatic hash added)
**Impact**: Safe filename created with unique hash

---

## Performance Tips

### 1. Enable LibreOffice
LibreOffice provides 10x better quality than ReportLab fallback for DOCX/PPTX.

### 2. Adjust Image Quality
For large batches, reduce `image_quality` to 85 for smaller file sizes.

### 3. Limit Table Rows
Set `max_table_rows=100` for faster processing of large spreadsheets.

### 4. Skip Unnecessary Outputs
Disable `generate_pdf=False` if only text-based RAG is needed.

---

## Next Steps

- **Stage 2**: See [STAGE2_MEDIA.md](STAGE2_MEDIA.md) for media processing
- **Stage 3**: See [STAGE3_DOCUMENT.md](STAGE3_DOCUMENT.md) for Docling processing
- **API Reference**: See [API_REFERENCE.md](API_REFERENCE.md) for complete API
