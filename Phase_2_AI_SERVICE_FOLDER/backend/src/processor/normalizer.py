"""
Document Normalizer Module

This module normalizes various document formats into either PDF or Markdown format
to prepare them for the document processing pipeline.

Supported Input Formats:
- Documents: DOCX, PPTX, ODT, RTF
- Web: HTML, MHTML
- Spreadsheets: XLSX, CSV
- Images: PNG, JPG, JPEG, BMP, TIFF
- Already normalized: PDF, MD, TXT

Output Formats:
- PDF: For image-based RAG retrieval (via Docling OCR)
- Markdown/Text: For text-based RAG retrieval
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
from tqdm import tqdm
import tempfile

from src.processor.utils import sanitize_filename_stem

# Import conversion libraries
try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

try:
    from pptx import Presentation
    PYTHON_PPTX_AVAILABLE = True
except ImportError:
    PYTHON_PPTX_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import img2pdf
    IMG2PDF_AVAILABLE = True
except ImportError:
    IMG2PDF_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


@dataclass
class NormalizerConfig:
    """Configuration for document normalization."""
    
    # Output format preferences
    generate_pdf: bool = True          # Generate PDF for image-based retrieval
    generate_markdown: bool = True     # Generate markdown for text-based retrieval
    
    # Image handling
    image_to_pdf: bool = True          # Convert standalone images to PDF
    image_quality: int = 95            # JPEG quality for image conversion
    
    # Spreadsheet handling
    excel_to_markdown: bool = True     # Convert Excel to Markdown tables
    csv_to_markdown: bool = True       # Convert CSV to Markdown tables
    max_table_rows: int = 1000         # Maximum rows to include in markdown
    
    # HTML handling
    html_preserve_formatting: bool = True  # Keep some HTML formatting in markdown
    
    # Document handling
    docx_extract_images: bool = True   # Extract embedded images from DOCX
    pptx_extract_images: bool = True   # Extract images from slides
    
    # PDF generation settings
    pdf_page_size: str = "A4"          # A4 or letter
    pdf_margin: float = 0.75           # Margin in inches
    
    # Output organization
    organize_by_type: bool = True      # Organize output by original file type


class DocumentNormalizer:
    """
    Normalizes various document formats into PDF and/or Markdown for RAG pipeline.
    
    This is the first stage in the processing pipeline:
    1. Normalizer converts everything to PDF/Markdown
    2. Document Processor processes the normalized files
    """
    
    def __init__(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[NormalizerConfig] = None
    ):
        """
        Initialize the Document Normalizer.
        
        Args:
            input_dir: Directory containing source documents
            output_dir: Directory for normalized outputs
            config: Normalization configuration
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or NormalizerConfig()
        
        # Create output directories
        self.pdf_dir = self.output_dir / "normalized_pdfs"
        self.markdown_dir = self.output_dir / "normalized_markdown"
        self.metadata_dir = self.output_dir / "normalization_metadata"
        self.originals_dir = self.output_dir / "original_files"  # Keep originals for Docling Stage 3
        self.excel_parsed_dir = self.output_dir / "excel_parsed"  # Custom Excel parser output
        
        for dir_path in [self.pdf_dir, self.markdown_dir, self.metadata_dir, self.originals_dir, self.excel_parsed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Track statistics
        self.stats = {
            "total_files": 0,
            "normalized_files": 0,
            "failed_files": 0,
            "by_type": {},
            "errors": []
        }
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_file = self.output_dir / "normalization.log"
        
    def normalize_batch(self) -> Dict:
        """
        Normalize all files in the input directory.
        
        Returns:
            Dictionary with processing statistics
        """
        print(f"Starting batch normalization from: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        
        # Find all files to process
        files_to_process = self._find_files()
        self.stats["total_files"] = len(files_to_process)
        
        print(f"Found {len(files_to_process)} files to normalize")
        
        # Process each file
        for file_path in tqdm(files_to_process, desc="Normalizing documents"):
            try:
                self._normalize_file(file_path)
                self.stats["normalized_files"] += 1
            except Exception as e:
                print(f"ERROR: Failed to normalize {file_path}: {str(e)}")
                self.stats["failed_files"] += 1
                self.stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # Save statistics
        self._save_statistics()
        
        print(f"Normalization complete. {self.stats['normalized_files']}/{self.stats['total_files']} files processed successfully")
        
        return self.stats
    
    def _find_files(self) -> List[Path]:
        """Find all supported files in input directory."""
        supported_extensions = {
            # Documents
            '.docx', '.doc', '.odt', '.rtf',
            # Presentations
            '.pptx', '.ppt', '.odp',
            # Web
            '.html', '.htm', '.mhtml', '.xhtml',  # Added .xhtml
            # Spreadsheets
            '.xlsx', '.xls', '.xlsm', '.csv',
            # Images
            '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp',  # Added .webp
            # Already normalized (just copy)
            '.pdf', '.md', '.txt',
            # Text formats
            '.adoc', '.asciidoc', '.asc',  # Added AsciiDoc
            '.vtt'  # Added WebVTT
        }
        
        files = []
        for ext in supported_extensions:
            files.extend(self.input_dir.rglob(f"*{ext}"))
        
        return sorted(files)
    
    def _normalize_file(self, file_path: Path):
        """
        Normalize a single file based on its type.
        
        Args:
            file_path: Path to the file to normalize
        """
        ext = file_path.suffix.lower()
        stem = file_path.stem
        
        # Track by type
        file_type = self._get_file_type(ext)
        self.stats["by_type"][file_type] = self.stats["by_type"].get(file_type, 0) + 1
        
        print(f"Normalizing {file_type}: {file_path.name}")
        
        # Get safe filename (truncate if too long) - Windows 260 char path limit
        safe_stem = self._get_safe_filename(stem)
        
        # Copy ALL files except media to original_files for Stage 3 Docling processing
        # Use safe_stem to avoid Windows path length issues
        media_extensions = {'.mp4', '.avi', '.mov', '.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a'}
        if ext not in media_extensions:
            original_copy = self.originals_dir / f"{safe_stem}{ext}"
            shutil.copy2(file_path, original_copy)
            print(f"  → Saved original for Docling: {original_copy.name}")
        
        # Dispatch to appropriate handler with safe filename
        if ext in ['.docx', '.doc']:
            self._normalize_docx(file_path, safe_stem)
        elif ext in ['.pptx', '.ppt']:
            self._normalize_pptx(file_path, safe_stem)
        elif ext in ['.html', '.htm', '.mhtml', '.xhtml']:
            self._normalize_html(file_path, safe_stem)
        elif ext in ['.xlsx', '.xlsm', '.xls']:
            self._normalize_excel(file_path, safe_stem)
        elif ext == '.csv':
            self._copy_to_originals_only(file_path, safe_stem)  # CSV: only copy to originals
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp']:
            self._normalize_image(file_path, safe_stem)
        elif ext == '.pdf':
            self._copy_pdf(file_path, safe_stem)
        elif ext == '.txt':
            self._txt_to_md(file_path, safe_stem)
        elif ext == '.md':
            self._copy_text(file_path, safe_stem)
        elif ext in ['.adoc', '.asciidoc', '.asc', '.vtt']:
            self._copy_to_originals_only(file_path, safe_stem)  # AsciiDoc/WebVTT: only copy to originals
        else:
            print(f"WARNING: Unsupported file type: {ext}")
    
    def _get_file_type(self, ext: str) -> str:
        """Get file type category from extension."""
        type_map = {
            '.docx': 'document', '.doc': 'document', '.odt': 'document', '.rtf': 'document',
            '.pptx': 'presentation', '.ppt': 'presentation', '.odp': 'presentation',
            '.html': 'web', '.htm': 'web', '.mhtml': 'web', '.xhtml': 'web',
            '.xlsx': 'spreadsheet', '.xls': 'spreadsheet', '.xlsm': 'spreadsheet',
            '.csv': 'csv',
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.bmp': 'image',
            '.tiff': 'image', '.tif': 'image', '.webp': 'image',
            '.pdf': 'pdf',
            '.adoc': 'asciidoc', '.asciidoc': 'asciidoc', '.asc': 'asciidoc',
            '.vtt': 'webvtt',
            '.md': 'markdown', '.txt': 'text'
        }
        return type_map.get(ext.lower(), 'unknown')
    
    def _get_safe_filename(self, stem: str, max_length: int = 50) -> str:
        """
        Get a safe filename by truncating long names and adding hash for uniqueness.
        
        Args:
            stem: Original filename stem (without extension)
            max_length: Maximum length for filename (default 50 chars for Windows path limits)
            
        Returns:
            Safe filename stem, truncated if needed with MD5 hash appended
        """
        stem = sanitize_filename_stem(stem)
        if len(stem) <= max_length:
            return stem
        
        # Truncate and add hash for uniqueness
        import hashlib
        hash_suffix = hashlib.md5(stem.encode()).hexdigest()[:8]
        truncated = stem[:max_length - 9]  # Leave room for underscore and hash
        return f"{truncated}_{hash_suffix}"
    
    # ======================== DOCX Normalization ========================
    
    def _normalize_docx(self, file_path: Path, stem: str):
        """Normalize DOCX files to PDF only (no markdown conversion)."""
        if not PYTHON_DOCX_AVAILABLE:
            print("WARNING: python-docx not available, skipping DOCX processing")
            return
        
        try:
            doc = Document(file_path)
            
            # Convert to PDF only - Try LibreOffice first (best quality)
            if self.config.generate_pdf:
                print("  → Trying LibreOffice for PDF conversion...")
                if not self._docx_to_pdf_libreoffice(file_path, stem):
                    # Fallback to ReportLab if LibreOffice not available
                    print("  → LibreOffice not available, using ReportLab (text-only)")
                    self._docx_to_pdf(doc, stem)
                else:
                    print("  → ✓ LibreOffice conversion successful (images preserved)")
                    
        except Exception as e:
            print(f"ERROR: Error processing DOCX {file_path}: {str(e)}")
            raise
    
    # Unused anymore but maybe keep
    def _docx_to_markdown(self, doc: 'Document') -> str:
        """Convert DOCX document to Markdown."""
        markdown_lines = []
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                markdown_lines.append("")
                continue
            
            # Check for heading style
            if para.style.name.startswith('Heading'):
                level = para.style.name.replace('Heading ', '')
                try:
                    level = int(level)
                    markdown_lines.append(f"{'#' * level} {text}\n")
                except:
                    markdown_lines.append(f"{text}\n")
            else:
                markdown_lines.append(f"{text}\n")
        
        # Extract tables
        for table in doc.tables:
            markdown_lines.append("\n")
            markdown_lines.append(self._table_to_markdown(table))
            markdown_lines.append("\n")
        
        return "\n".join(markdown_lines)
    
    # Unused anymore but maybe keep
    def _table_to_markdown(self, table) -> str:
        """Convert a DOCX table to Markdown format."""
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
        
        if len(rows) > 1:
            # Add separator after header
            header = rows[0]
            separator = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
            return "\n".join([header, separator] + rows[1:])
        elif rows:
            return rows[0]
        return ""
    
    # Convert docx to pdf using libreoffice
    def _docx_to_pdf_libreoffice(self, file_path: Path, stem: str) -> bool:
        """Convert DOCX/PPTX to PDF using LibreOffice (best quality, preserves images)."""
        # Use safe stem to avoid Windows path length issues
        pdf_path = self.pdf_dir / f"{stem}.pdf"
        
        try:
            import subprocess
            import sys
            
            # Try platform-specific LibreOffice paths
            if sys.platform == 'win32':
                soffice_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                ]
            elif sys.platform == 'darwin':  # macOS
                soffice_paths = [
                    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                ]
            else:  # Linux and other Unix-like systems
                soffice_paths = [
                    "/usr/bin/soffice",
                    "/usr/local/bin/soffice",
                    "soffice",  # Try PATH
                ]
            
            # Find LibreOffice by checking if executable exists
            # Note: We check file existence instead of running --version because
            # soffice.exe --version can hang with window suppression flags
            soffice = None
            for path in soffice_paths:
                if Path(path).exists():
                    soffice = path
                    break
            
            if not soffice:
                print("    ✗ LibreOffice not found in system")
                print("    ℹ Install LibreOffice from: https://www.libreoffice.org/download/")
                return False
            
            print(f"    ✓ Found LibreOffice: {soffice}")
            
            # Convert using LibreOffice with window suppression
            cmd = [
                soffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(self.pdf_dir),
                str(file_path)
            ]
            
            # Configure subprocess to hide window on Windows
            conversion_kwargs = {'capture_output': True, 'timeout': 60}
            
            if sys.platform == 'win32':
                # Use STARTUPINFO with SW_HIDE to prevent console window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                conversion_kwargs['startupinfo'] = startupinfo
                conversion_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(cmd, **conversion_kwargs)
            
            # LibreOffice outputs with original filename, rename if needed
            output_pdf = self.pdf_dir / f"{file_path.stem}.pdf"
            if output_pdf.exists() and output_pdf != pdf_path:
                output_pdf.rename(pdf_path)
            
            if pdf_path.exists():
                return True
            else:
                print(f"    ✗ LibreOffice conversion failed (output not found)")
                return False
            
        except Exception as e:
            print(f"    ✗ LibreOffice error: {e}")
            return False
    
    # Fallback PDF conversion using ReportLab (text-only)
    def _docx_to_pdf(self, doc: 'Document', stem: str):
        """Convert DOCX document to PDF using ReportLab (fallback only).
        Uses safe stem to avoid Windows path length issues.
        """
        if not REPORTLAB_AVAILABLE:
            print("WARNING: ReportLab not available, cannot convert DOCX to PDF")
            return
        
        # Use safe stem
        pdf_path = self.pdf_dir / f"{stem}.pdf"
        
        try:
            # Create PDF document
            pdf_doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4 if self.config.pdf_page_size == "A4" else letter,
                leftMargin=self.config.pdf_margin * inch,
                rightMargin=self.config.pdf_margin * inch,
                topMargin=self.config.pdf_margin * inch,
                bottomMargin=self.config.pdf_margin * inch
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Add paragraphs
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    # Determine style based on heading
                    if para.style.name.startswith('Heading'):
                        style = styles['Heading1']
                    else:
                        style = styles['Normal']
                    
                    story.append(Paragraph(text, style))
                    story.append(Spacer(1, 0.2 * inch))
            
            pdf_doc.build(story)
            print(f"Created PDF: {pdf_path}")
        
        except Exception as e:
            print(f"ERROR: Error creating PDF from DOCX: {str(e)}")
    
    # ======================== PPTX Normalization ========================
    
    def _normalize_pptx(self, file_path: Path, stem: str):
        """Normalize PPTX files to PDF and Markdown."""
        if not PYTHON_PPTX_AVAILABLE:
            print("WARNING: python-pptx not available, skipping PPTX processing")
            return
        
        try:
            prs = Presentation(file_path)
            
            # Convert to PDF only - Try LibreOffice first (best quality, preserves images)
            if self.config.generate_pdf:
                print("  → Trying LibreOffice for PDF conversion...")
                if not self._docx_to_pdf_libreoffice(file_path, stem):
                    # Fallback to ReportLab if LibreOffice not available
                    print("  → LibreOffice not available, using ReportLab (text-only)")
                    self._pptx_to_pdf(prs, stem)
                else:
                    print("  → ✓ LibreOffice conversion successful (images preserved)")
                    
        except Exception as e:
            print(f"ERROR: Error processing PPTX {file_path}: {str(e)}")
            raise
    
    # Unused anymore but maybe keep
    def _pptx_to_markdown(self, prs: 'Presentation') -> str:
        """Convert PPTX presentation to Markdown."""
        markdown_lines = []
        
        for idx, slide in enumerate(prs.slides, 1):
            markdown_lines.append(f"## Slide {idx}\n")
            
            # Extract text from shapes
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    markdown_lines.append(f"{shape.text.strip()}\n")
            
            markdown_lines.append("\n---\n")
        
        return "\n".join(markdown_lines)
    
    # Unused anymore but maybe keep
    def _pptx_to_pdf(self, prs: 'Presentation', stem: str):
        """Convert PPTX presentation to PDF using ReportLab (fallback only).
        Uses safe stem to avoid Windows path length issues."""
        if not REPORTLAB_AVAILABLE:
            print("WARNING: ReportLab not available, cannot convert PPTX to PDF")
            return
        
        # Use safe stem
        pdf_path = self.pdf_dir / f"{stem}.pdf"
        
        try:
            pdf_doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4 if self.config.pdf_page_size == "A4" else letter
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            for idx, slide in enumerate(prs.slides, 1):
                # Add slide header
                story.append(Paragraph(f"Slide {idx}", styles['Heading1']))
                story.append(Spacer(1, 0.3 * inch))
                
                # Add text content
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        story.append(Paragraph(shape.text.strip(), styles['Normal']))
                        story.append(Spacer(1, 0.2 * inch))
                
                # Page break between slides
                if idx < len(prs.slides):
                    story.append(PageBreak())
            
            pdf_doc.build(story)
            print(f"Created PDF: {pdf_path}")
        
        except Exception as e:
            print(f"ERROR: Error creating PDF from PPTX: {str(e)}")
    
    # ======================== HTML Normalization ========================
    
    def _normalize_html(self, file_path: Path, stem: str):
        """Normalize HTML to Markdown and PDF."""
        if not BS4_AVAILABLE:
            print("WARNING: BeautifulSoup not available, skipping HTML processing")
            return
        
        try:
            # Convert to PDF using LibreOffice (preserves layout, images, styling)
            if self.config.generate_pdf:
                print("  → Trying LibreOffice for HTML to PDF conversion...")
                if self._html_to_pdf_libreoffice(file_path, stem):
                    print("  → ✓ LibreOffice HTML→PDF conversion successful")
                else:
                    print("  → LibreOffice not available for HTML, PDF not generated")
        
        except Exception as e:
            print(f"ERROR: Error processing HTML {file_path}: {str(e)}")
            raise
    
    def _html_to_pdf_libreoffice(self, file_path: Path, stem: str) -> bool:
        """Convert HTML to PDF using LibreOffice (preserves layout, images, CSS styling)."""
        # Use safe stem to avoid Windows path length issues
        pdf_path = self.pdf_dir / f"{stem}.pdf"
        
        try:
            import subprocess
            import sys
            
            # Try platform-specific LibreOffice paths
            if sys.platform == 'win32':
                soffice_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                ]
            elif sys.platform == 'darwin':  # macOS
                soffice_paths = [
                    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                ]
            else:  # Linux and other Unix-like systems
                soffice_paths = [
                    "/usr/bin/soffice",
                    "/usr/local/bin/soffice",
                    "soffice",  # Try PATH
                ]
            
            # Find LibreOffice
            soffice = None
            for path in soffice_paths:
                if Path(path).exists():
                    soffice = path
                    break
            
            if not soffice:
                return False
            
            print(f"    ✓ Found LibreOffice for HTML: {soffice}")
            
            # Convert HTML to PDF using LibreOffice with window suppression
            cmd = [
                soffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(self.pdf_dir),
                str(file_path)
            ]
            
            # Configure subprocess to hide window on Windows
            conversion_kwargs = {'capture_output': True, 'timeout': 60}
            
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                conversion_kwargs['startupinfo'] = startupinfo
                conversion_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(cmd, **conversion_kwargs)
            
            # LibreOffice outputs with original filename, rename to safe name if needed
            output_pdf = self.pdf_dir / f"{file_path.stem}.pdf"
            if output_pdf.exists() and output_pdf != pdf_path:
                output_pdf.rename(pdf_path)
            
            if pdf_path.exists():
                return True
            else:
                return False
        
        except Exception as e:
            print(f"    ✗ LibreOffice HTML conversion failed: {str(e)}")
            return False
    
    # ======================== Excel Normalization ========================
    
    def _normalize_excel(self, file_path: Path, stem: str):
        """Parse Excel files using custom XML-based parser (xlsx_reader_v2).
        
        Produces structured JSON in excel_parsed/ that preserves:
        - Table structures with proper headers
        - Charts with data series
        - Shapes and embedded images
        - Merged cells, hyperlinks, styles
        
        The JSON is consumed later by _run_excel_processing() in the pipeline
        to produce RAG-ready chunks via ExcelPreprocessor.
        """
        ext = file_path.suffix.lower()
        
        # Only our custom parser handles .xlsx and .xlsm natively
        if ext in ('.xlsx', '.xlsm'):
            try:
                from .xlsx_reader_v2 import process_excel_file
                
                json_output = process_excel_file(
                    excel_path=file_path,
                    output_dir=self.excel_parsed_dir,
                    parsed_parent=self.excel_parsed_dir / "_parsed",
                )
                print(f"  → ✓ Excel parsed to JSON: {json_output.name}")
                
            except Exception as e:
                print(f"  → ✗ Custom Excel parser failed: {e}")
                print(f"  → Falling back to Docling processing")
                # Keep the copy in originals_dir so Docling can try
        
        elif ext == '.xls':
            # .xls (legacy binary format) — keep in originals for Docling
            print(f"  → .xls file — will be processed by Docling")
    
    # ======================== CSV Normalization ========================
    
    def _normalize_csv(self, file_path: Path, stem: str):
        """Normalize CSV files - no conversion needed, Docling will handle it."""
        # CSV files are already copied to original_files for Docling processing
        # No markdown conversion needed here
        print(f"  → CSV file ready for Docling processing")
        pass
    
    def _copy_to_originals_only(self, file_path: Path, stem: str):
        """Copy files to original_files only (already done in _normalize_file)."""
        # File already copied to original_files for Docling processing
        print(f"  → File ready for Docling processing")
        pass
        
    # ======================== Image Normalization ========================
    
    def _normalize_image(self, file_path: Path, stem: str):
        """Normalize image files - NO PDF conversion, let Docling handle natively."""
        # CRITICAL FIX: Do NOT convert images to PDF!
        # Docling processes images better than converted PDFs
        # Images already copied to original_files/, no additional processing needed
        
        print(f"  → Image ready for Docling native processing (no PDF conversion)")
        
        # Note: Image was already copied to original_files/ in _normalize_file()
        # Docling will process it directly with VLM, picture classification, etc.
    
    # ======================== Direct Copy Operations ========================
    
    def _copy_pdf(self, file_path: Path, stem: str):
        """Copy PDF files to normalized directory with safe name."""
        if self.config.generate_pdf:
            dest = self.pdf_dir / f"{stem}.pdf"
            shutil.copy(file_path, dest)
            print(f"Copied PDF: {dest.name}")
    
    def _txt_to_md(self, file_path: Path, stem: str):
        """Convert TXT to MD format with safe name."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use safe stem
        md_path = self.markdown_dir / f"{stem}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  → Converted TXT to MD: {md_path.name}")
    
    def _copy_text(self, file_path: Path, stem: str):
        """Copy markdown files to normalized directory with safe name."""
        if self.config.generate_markdown:
            dest = self.markdown_dir / f"{stem}.md"
            shutil.copy(file_path, dest)
            print(f"  → Copied markdown file: {dest.name}")
    
    # ======================== Helper Methods ========================
    
    def _save_markdown(self, stem: str, content: str):
        """Save markdown content to file."""
        md_path = self.markdown_dir / f"{stem}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created markdown: {md_path}")
    
    def _save_statistics(self):
        """Save processing statistics to JSON."""
        stats_path = self.metadata_dir / "normalization_stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Saved statistics to: {stats_path}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            print(f"ERROR: Error during normalization: {exc_val}")
        return False


# ======================== Utility Functions ========================

def normalize_documents(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    config: Optional[NormalizerConfig] = None
) -> Dict:
    """
    Convenience function to normalize documents.
    
    Args:
        input_dir: Directory containing source documents
        output_dir: Directory for normalized outputs
        config: Optional normalization configuration
    
    Returns:
        Dictionary with processing statistics
    """
    with DocumentNormalizer(input_dir, output_dir, config) as normalizer:
        return normalizer.normalize_batch()


if __name__ == "__main__":
    # Example usage
    config = NormalizerConfig(
        generate_pdf=True,
        generate_markdown=True,
        excel_to_markdown=True,
        csv_to_markdown=True
    )
    
    stats = normalize_documents(
        input_dir="input",
        output_dir="output/normalized",
        config=config
    )
    
    print(f"\nNormalization Summary:")
    print(f"Total files: {stats['total_files']}")
    print(f"Successfully normalized: {stats['normalized_files']}")
    print(f"Failed: {stats['failed_files']}")
    print(f"\nBy type: {stats['by_type']}")
