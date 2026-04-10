"""
Advanced Multimodal Document Processor using Docling

This module provides a comprehensive document processing solution that leverages
all of Docling's advanced features for multimodal RAG pipeline preparation.

Features:
- Advanced PDF understanding with layout analysis
- OCR support for scanned documents and images
- Audio processing with ASR
- Visual Language Model integration
- Multimodal export in structured formats
- GPU acceleration support
- Comprehensive metadata extraction
"""

from __future__ import annotations

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
from tqdm import tqdm

# Docling imports - with error handling for different versions
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PipelineOptions,
        PdfPipelineOptions,
    )

    # Try to import advanced features (may not be available in all versions)
    try:
        from docling.datamodel.pipeline_options import TableStructureOptions
    except ImportError:
        TableStructureOptions = None

    try:
        from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    except ImportError:
        DoclingParseDocumentBackend = None

    try:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    except ImportError:
        PyPdfiumDocumentBackend = None

    DOCLING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Docling not fully available: {e}")
    DOCLING_AVAILABLE = False

    # Create dummy classes for development/testing without Docling
    class DocumentConverter:
        def __init__(self, **kwargs):
            raise ImportError("Docling not installed. Please install with: pip install docling[all]")

        def convert(self, source):
            raise ImportError("Docling not installed")

    class InputFormat:
        PDF = "pdf"
        IMAGE = "image"
        PNG = "png"
        JPEG = "jpeg"
        AUDIO = "audio"
        DOCX = "docx"
        PPTX = "pptx"
        XLSX = "xlsx"
        HTML = "html"
        MD = "md"
        CSV = "csv"
        ASCIIDOC = "asciidoc"
        VTT = "vtt"

    class PipelineOptions:
        def __init__(self):
            pass

# Handle optional components with fallbacks
try:
    from docling.datamodel.pipeline_options import OcrOptions, TesseractOcrOptions, EasyOcrOptions, RapidOcrOptions
except ImportError:
    class OcrOptions:
        pass
    class TesseractOcrOptions:
        kind = "tesserocr"
        def __init__(self, **kwargs):
            pass
    class EasyOcrOptions:
        kind = "easyocr"
        def __init__(self, **kwargs):
            pass
    class RapidOcrOptions:
        kind = "rapidocr"
        def __init__(self, **kwargs):
            pass

try:
    from docling.datamodel.pipeline_options import VlmPipelineOptions
except ImportError:
    class VlmPipelineOptions:
        def __init__(self, **kwargs):
            pass

try:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmOptions
except ImportError:
    class PictureDescriptionVlmOptions:
        def __init__(self, **kwargs):
            pass

try:
    from docling.datamodel.pipeline_options import AsrPipelineOptions
except ImportError:
    class AsrPipelineOptions:
        def __init__(self, **kwargs):
            pass

# Additional imports for processing
from PIL import Image
from io import BytesIO
import torch

# ── PyTorch optimisations for low-SM GPUs (e.g. RTX A1000 with 16 SMs) ──
# 1. Enable TensorFloat32 for faster float32 matmul with minimal precision loss
torch.set_float32_matmul_precision('high')

# 2. Disable torch.compile / inductor backend.
#    PyTorch ≥ 2.6 uses torch.compile by default in many code paths (Transformers,
#    Docling models). The inductor backend's max_autotune_gemm mode requires more
#    SMs than a 16-SM laptop GPU has, causing "Not enough SMs" warnings and pipeline
#    failures. Suppressing it forces eager-mode execution (same as PyTorch ≤ 2.5).
import torch._dynamo
torch._dynamo.config.suppress_errors = True   # Don't crash on compile failures
torch._inductor.config.triton.autotune_pointwise = False  # type: ignore[attr-defined]
import os
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")         # Fully disable dynamo/compile

from loguru import logger

from src.processor.utils import sanitize_filename_stem


@dataclass
class ProcessingConfig:
    """Configuration class for document processing settings."""
    
    # General settings
    use_gpu: bool = True
    enable_ocr: bool = True
    enable_vlm: bool = True
    enable_asr: bool = True
    
    # OCR settings
    ocr_engine: str = "rapidocr"  # tesseract, easyocr, rapidocr - using rapidocr as it's working
    ocr_languages: List[str] = None
    
    # VLM settings
    vlm_model: str = "granite_docling"  # granite_docling, custom
    
    # ASR settings
    asr_model: str = "whisper"
    
    # Export settings
    export_markdown: bool = True
    export_images: bool = False  # Disabled by default for 3x faster processing
    export_tables: bool = False  # Disabled by default for 3x faster processing
    export_metadata: bool = True
    
    # Image filtering settings - FILTER OUT SMALL ICONS AND LOW QUALITY IMAGES
    min_image_width: int = 100      # Minimum width in pixels (filter out small icons)
    min_image_height: int = 100     # Minimum height in pixels (filter out small icons)
    min_image_area: int = 10000     # Minimum total area in pixels (100x100 = 10,000)
    
    # Output organization
    create_subfolder_per_doc: bool = True
    preserve_structure: bool = True
    
    def __post_init__(self):
        if self.ocr_languages is None:
            self.ocr_languages = ["eng"]  # Default to English only to avoid EasyOCR compatibility issues


class MultimodalDocumentProcessor:
    """
    Advanced multimodal document processor leveraging Docling's full capabilities.
    
    This processor handles various document formats and prepares them for GenAI
    consumption in a multimodal RAG pipeline, with special focus on educational
    content processing for HCMUT.
    
    Renamed from DocumentProcessor to avoid confusion with Docling's internal classes.
    """
    
    # Formats supported directly by Docling
    # These correspond to InputFormat enums in Docling and are automatically handled
    DOCLING_SUPPORTED_FORMATS = {
        'pdf': ['.pdf'],                    # InputFormat.PDF - Enhanced with custom pipeline
        'office': ['.docx', '.pptx', '.xlsx'],  # InputFormat.DOCX, PPTX, XLSX - Default Docling processing
        'image': ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'],  # InputFormat.IMAGE - Enhanced with PDF pipeline, added WEBP
        'web': ['.html', '.htm', '.xhtml'],           # InputFormat.HTML - Default Docling processing, added XHTML
        'text': ['.md', '.txt'],            # InputFormat.MD, TXT - Default Docling processing
        'csv': ['.csv'],                    # InputFormat.CSV - Default Docling processing
        'asciidoc': ['.adoc', '.asciidoc', '.asc'],  # InputFormat.ASCIIDOC - Default Docling processing
        'webvtt': ['.vtt']                  # InputFormat.VTT - Default Docling processing
        # NOTE: Audio/Video are handled by media_processor.py, not here
        # Transcripts will be saved as .md for Docling processing
    }
    
    @property
    def SUPPORTED_FORMATS(self):
        """Supported formats for Docling processing."""
        return self.DOCLING_SUPPORTED_FORMATS
    
    def __init__(self, 
                 input_dir: Union[str, Path],
                 output_dir: Union[str, Path],
                 config: Optional[ProcessingConfig] = None):
        """
        Initialize the document processor.
        
        Args:
            input_dir: Directory containing input documents
            output_dir: Directory for processed outputs
            config: Processing configuration settings
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or ProcessingConfig()
        
        # Setup directories
        self._setup_directories()
        
        # Setup logging
        self._setup_logging()
        
        # Initialize converters
        self._initialize_converters()
        
        # Track processing statistics
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'processing_time': 0,
            'file_types': {},
            'errors': []
        }
        
        logger.info(f"DocumentProcessor initialized")
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"GPU support: {self.config.use_gpu and torch.cuda.is_available()}")
    
    def _setup_directories(self) -> None:
        # Create base output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logs directory (only needed for global logging)
        (self.output_dir / "logs").mkdir(exist_ok=True)
    
    def _setup_logging(self) -> None:
        """Configure logging for the processor."""
        log_file = self.output_dir / "logs" / f"processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logger.add(
            log_file,
            rotation="10 MB",
            retention="10 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}"
        )
        
        logger.info("Logging initialized")
    
    def _initialize_converters(self) -> None:
        """Initialize Docling converters with comprehensive format options for all supported document types."""
        try:
            # Try to create enhanced converter with comprehensive options for ALL supported formats
            try:
                from docling.datamodel.pipeline_options import PdfPipelineOptions, PipelineOptions
                from docling.document_converter import FormatOption
                from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
                from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
                from docling.pipeline.simple_pipeline import SimplePipeline
                
                # Try to import additional backends (may not be available in all versions)
                try:
                    from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
                    ADVANCED_BACKEND = DoclingParseV4DocumentBackend
                except ImportError:
                    try:
                        from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
                        ADVANCED_BACKEND = DoclingParseDocumentBackend
                    except ImportError:
                        ADVANCED_BACKEND = PyPdfiumDocumentBackend
                
                # Try to import ASR pipeline for audio processing
                try:
                    from docling.pipeline.asr_pipeline import AsrPipeline
                    ASR_AVAILABLE = True
                except ImportError:
                    AsrPipeline = None
                    ASR_AVAILABLE = False
                
                # Configure PDF pipeline options with ADVANCED settings for better image extraction
                vlm_options = self._get_vlm_options() if self.config.enable_vlm else None
                
                # DEBUG: Print VLM configuration
                logger.info(f"🔍 VLM Debug - enable_vlm: {self.config.enable_vlm}")
                logger.info(f"🔍 VLM Debug - vlm_options: {vlm_options}")
                if vlm_options:
                    logger.info(f"🔍 VLM Debug - repo_id: {getattr(vlm_options, 'repo_id', 'NOT_SET')}")
                    logger.info(f"🔍 VLM Debug - picture_area_threshold: {getattr(vlm_options, 'picture_area_threshold', 'NOT_SET')}")
                    logger.info(f"🔍 VLM Debug - batch_size: {getattr(vlm_options, 'batch_size', 'NOT_SET')}")
                
                # CRITICAL FIX: Enable full VLM and image processing for images
                # Week0506 had this enabled and worked well for input images
                # Images need picture description and classification for good OCR results
                
                # FORCE VLM ON for images (override config if needed)
                use_vlm = self.config.enable_vlm if hasattr(self.config, 'enable_vlm') else True
                logger.info(f"🔥 FORCING VLM: {use_vlm} (config: {self.config.enable_vlm})")
                
                pdf_options = PdfPipelineOptions(
                    do_ocr=self.config.enable_ocr,                    # Enable OCR
                    do_table_structure=True,                          # Enable table structure detection
                    generate_picture_images=True,                     # CRITICAL: Enable image extraction
                    generate_page_images=True,                        # Generate full page images for better extraction
                    generate_table_images=True,                       # Generate table images
                    do_picture_classification=True,                   # Enable advanced picture classification
                    do_picture_description=use_vlm,                   # Enable picture description with VLM
                    images_scale=2.0,                                 # HIGHER SCALE: 2x resolution for better image quality
                    ocr_options=self._get_ocr_options(),              # OCR configuration
                    picture_description_options=vlm_options if use_vlm else None,  # VLM options
                )
                
                # DEBUG: Print final pipeline options
                logger.info(f"🔍 Pipeline Debug - do_picture_description: {pdf_options.do_picture_description}")
                logger.info(f"🔍 Pipeline Debug - picture_description_options set: {pdf_options.picture_description_options is not None}")
                
                # COMPREHENSIVE FORMAT OPTIONS - Configure supported formats with optimized settings
                format_options = {}
                
                # PDF documents with advanced processing - PRIORITY FORMAT
                format_options[InputFormat.PDF] = FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=ADVANCED_BACKEND,  # Use best available backend
                    pipeline_options=pdf_options
                )
                
                # IMAGE formats with same advanced pipeline as PDF (for OCR and analysis)
                format_options[InputFormat.IMAGE] = FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=ADVANCED_BACKEND,
                    pipeline_options=pdf_options  # Same options for image processing
                )
                
                # For other formats, let DocumentConverter use its default configurations
                # This ensures compatibility while still getting enhanced PDF/Image processing
                
                logger.info(f"Configured enhanced processing for: PDF, IMAGE formats")
                logger.info(f"Other formats (DOCX, PPTX, XLSX, HTML, MD, AUDIO) will use Docling defaults")
                
                # Define allowed formats based on what we support
                # This ensures DocumentConverter only processes files we can handle
                allowed_formats = [
                    InputFormat.PDF,
                    InputFormat.DOCX,
                    InputFormat.PPTX,
                    InputFormat.XLSX,
                    InputFormat.HTML,
                    InputFormat.IMAGE,
                    InputFormat.MD,
                    InputFormat.CSV,
                    InputFormat.ASCIIDOC,
                    InputFormat.VTT
                    # Note: AUDIO handled by media_processor separately
                ]
                
                # Create converter with enhanced format options for priority formats
                # Docling will automatically handle other formats with their default configurations
                self.converter = DocumentConverter(
                    allowed_formats=allowed_formats,
                    format_options=format_options
                )
                
                logger.info("MultimodalDocumentProcessor converters initialized successfully:")
                logger.info(f"  ✅ Enhanced formats: {list(format_options.keys())}")
                logger.info(f"  📄 PDF: OCR-optimized pipeline (text extraction only)")
                logger.info(f"  🖼️  Images: Same OCR pipeline as PDF")
                logger.info(f"  📊 Office docs: Default Docling processing (DOCX, PPTX, XLSX)")
                logger.info(f"  🌐 Web docs: Default Docling processing (HTML)")
                logger.info(f"  📝 Text docs: Default Docling processing (MD)")
                logger.info(f"  ⚡ Full processing mode: VLM={use_vlm}, image processing=True, scale=2.0")
                
                if ASR_AVAILABLE and self.config.enable_asr:
                    logger.info(f"  🎵 Audio: ASR pipeline available")
                else:
                    logger.info(f"  🎵 Audio: ASR not available or disabled")
                
            except Exception as e:
                logger.warning(f"Enhanced format options failed: {e}, using basic converter")
                # Fallback to basic converter with allowed formats only
                allowed_formats = [
                    InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.XLSX,
                    InputFormat.HTML, InputFormat.IMAGE, InputFormat.MD, InputFormat.CSV,
                    InputFormat.ASCIIDOC, InputFormat.VTT
                ]
                self.converter = DocumentConverter(allowed_formats=allowed_formats)
                logger.info("Basic document converter initialized (fallback mode)")
            
            logger.info(f"OCR engine config: {self.config.ocr_engine}")
            logger.info(f"VLM enabled: {self.config.enable_vlm}")
            logger.info(f"ASR enabled: {self.config.enable_asr}")
            
        except Exception as e:
            logger.error(f"Failed to initialize converters: {e}")
            # Last resort - basic converter with allowed formats only
            try:
                allowed_formats = [
                    InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.XLSX,
                    InputFormat.HTML, InputFormat.IMAGE, InputFormat.MD, InputFormat.CSV,
                    InputFormat.ASCIIDOC, InputFormat.VTT
                ]
                self.converter = DocumentConverter(allowed_formats=allowed_formats)
                logger.info("Fallback to most basic converter with allowed formats")
            except:
                # Absolute last resort - no parameters
                self.converter = DocumentConverter()
                logger.info("Fallback to default converter")
    
    def _get_ocr_options(self) -> Optional[OcrOptions]:
        """Get OCR configuration based on settings."""
        # Always provide OCR options for pipeline validation, even if OCR is disabled
        # The do_ocr flag in PdfPipelineOptions controls whether OCR is actually used
        try:
            if self.config.ocr_engine == "rapidocr":
                return RapidOcrOptions(
                    lang=self.config.ocr_languages
                )
            elif self.config.ocr_engine == "tesseract":
                return TesseractOcrOptions(
                    lang=self.config.ocr_languages
                )
            elif self.config.ocr_engine == "easyocr":
                # EasyOCR uses different language codes - map common ones
                easyocr_langs = []
                for lang in self.config.ocr_languages:
                    if lang == "eng" or lang == "en":
                        easyocr_langs.append("en")
                    elif lang == "deu" or lang == "de":
                        easyocr_langs.append("de")
                    elif lang == "fra" or lang == "fr":
                        easyocr_langs.append("fr")
                    elif lang == "spa" or lang == "es":
                        easyocr_langs.append("es")
                    elif lang == "chi_sim" or lang == "zh":
                        easyocr_langs.append("ch_sim")
                    else:
                        # Try the original language code as fallback
                        easyocr_langs.append(lang)
                
                # Ensure we have at least English
                if not easyocr_langs:
                    easyocr_langs = ["en"]
                
                logger.info(f"EasyOCR using languages: {easyocr_langs}")
                return EasyOcrOptions(
                    lang=easyocr_langs,
                    use_gpu=self.config.use_gpu
                )
            else:
                logger.warning(f"Unknown OCR engine: {self.config.ocr_engine}, falling back to rapidocr")
                return RapidOcrOptions(
                    lang=self.config.ocr_languages
                )
        except Exception as e:
            logger.warning(f"Failed to configure {self.config.ocr_engine}, falling back to rapidocr: {e}")
            return RapidOcrOptions(
                lang=self.config.ocr_languages
            )
    
    def _get_vlm_options(self) -> Optional[PictureDescriptionVlmOptions]:
        """Get VLM configuration based on settings."""
        if not self.config.enable_vlm:
            return None
        
        # Configure VLM options for enhanced visual understanding
        # Use SmolVLM model which is the default and was working in our tests
        # Force a low area threshold so small images (logos/screenshots) are not skipped
        # Keep batch_size low to avoid GPU memory exhaustion during Docling processing
        return PictureDescriptionVlmOptions(
            repo_id="HuggingFaceTB/SmolVLM-256M-Instruct",
            batch_size=4,
            scale=2,
            picture_area_threshold=0.0,
            prompt="Describe this image in a few concise sentences.",
            generation_config={"max_new_tokens": 200, "do_sample": False}
        )
    
    def _get_asr_options(self) -> Optional[AsrPipelineOptions]:
        """Get ASR configuration based on settings."""
        if not self.config.enable_asr:
            return None
        
        return AsrPipelineOptions(
            model=self.config.asr_model,
            language="auto"  # Auto-detect language
        )

    def get_file_type(self, file_path: Path) -> str:
        """
        Determine the file type category.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type category as string
        """
        suffix = file_path.suffix.lower()
        
        for file_type, extensions in self.SUPPORTED_FORMATS.items():
            if suffix in extensions:
                return file_type
        
        return 'unknown'
    
    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if file format is supported.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if format is supported
        """
        return self.get_file_type(file_path) != 'unknown'
    
    def scan_input_directory(self) -> List[Path]:
        """
        Scan input directory for supported files.
        
        Returns:
            List of supported file paths
        """
        supported_files = []
        
        if not self.input_dir.exists():
            logger.error(f"Input directory does not exist: {self.input_dir}")
            return supported_files
        
        # Recursively scan for files
        for file_path in self.input_dir.rglob("*"):
            if file_path.is_file() and self.is_supported_format(file_path):
                supported_files.append(file_path)
        
        # Update statistics
        self.stats['total_files'] = len(supported_files)
        
        # Count by file type
        for file_path in supported_files:
            file_type = self.get_file_type(file_path)
            self.stats['file_types'][file_type] = self.stats['file_types'].get(file_type, 0) + 1
        
        logger.info(f"Found {len(supported_files)} supported files")
        logger.info(f"File types distribution: {self.stats['file_types']}")
        
        return supported_files
    
    def _convert_txt_to_md(self, txt_path: Path) -> Path:
        """Convert TXT file to markdown for Docling processing."""
        # Read the text file
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(txt_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Create markdown content
        md_content = f"# {txt_path.stem}\n\n{content}"
        
        # Save as temporary markdown file
        temp_md_path = txt_path.parent / f"{txt_path.stem}_temp.md"
        with open(temp_md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return temp_md_path
    
    def _create_fallback_converter(self):
        """Create a lightweight fallback converter without VLM for retry on failure."""
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions, PipelineOptions
            from docling.document_converter import FormatOption
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

            # Simple OCR-only pipeline — no VLM, no picture description, lower scale
            pdf_options = PdfPipelineOptions(
                do_ocr=self.config.enable_ocr,
                do_table_structure=True,
                generate_picture_images=True,
                generate_page_images=False,          # Skip full page images
                generate_table_images=True,
                do_picture_classification=False,      # Skip picture classification
                do_picture_description=False,         # NO VLM
                images_scale=1.0,                     # Lower scale to save memory
                ocr_options=self._get_ocr_options(),
            )

            format_options = {
                InputFormat.PDF: FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pdf_options
                ),
                InputFormat.IMAGE: FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pdf_options
                ),
            }

            allowed_formats = [
                InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.XLSX,
                InputFormat.HTML, InputFormat.IMAGE, InputFormat.MD, InputFormat.CSV,
                InputFormat.ASCIIDOC, InputFormat.VTT
            ]

            return DocumentConverter(
                allowed_formats=allowed_formats,
                format_options=format_options
            )
        except Exception as e:
            logger.warning(f"Could not create fallback converter: {e}")
            return None

    def process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single file using Docling's capabilities.
        If the primary (VLM-enabled) pipeline fails, retries with a
        lightweight OCR-only fallback pipeline.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Dictionary containing processing results and metadata.

            ```
            {
                'file_path': str,
                'file_size': int,
                'file_type': str,
                'processing_time': float,
                'pages': int,
                'success': bool,
                'doc_object': DoclingDocument or None,
                'result_object': ConversionResult or None,
                'error': str or None
            }
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Ensure file_path is a Path object
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            # Handle TXT files by converting to markdown first
            actual_file_path = file_path
            temp_file_created = False
            
            if file_path.suffix.lower() == '.txt':
                logger.info(f"Converting TXT file to markdown: {file_path}")
                actual_file_path = self._convert_txt_to_md(file_path)
                temp_file_created = True
            
            # --- Primary attempt with full pipeline ---
            result = None
            used_fallback = False
            try:
                result = self.converter.convert(str(actual_file_path))
            except Exception as primary_err:
                logger.warning(
                    f"Primary pipeline failed for {file_path.name}: {primary_err}. "
                    "Retrying with lightweight OCR-only fallback..."
                )
                # --- Fallback attempt without VLM ---
                fallback = self._create_fallback_converter()
                if fallback is not None:
                    try:
                        result = fallback.convert(str(actual_file_path))
                        used_fallback = True
                        logger.info(f"✅ Fallback pipeline succeeded for {file_path.name}")
                    except Exception as fallback_err:
                        raise Exception(
                            f"Both pipelines failed. "
                            f"Primary: {primary_err} | Fallback: {fallback_err}"
                        ) from fallback_err
                else:
                    raise primary_err
            
            if not result:
                raise Exception("Conversion returned no result")
            
            # Get the DoclingDocument
            pipeline_label = " (fallback OCR-only)" if used_fallback else ""
            print(f"✓ Document converted successfully{pipeline_label}")
            doc = result.document
            
            # Extract processing information
            processing_info = {
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'file_type': self.get_file_type(file_path),
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'pages': getattr(doc, 'page_count', None),
                'success': True,
                'doc_object': doc,
                'result_object': result,
                'used_fallback': used_fallback
            }
            
            logger.info(f"Successfully processed {file_path} in {processing_info['processing_time']:.2f}s{pipeline_label}")
            
            # Cleanup temporary file if created
            if temp_file_created and actual_file_path.exists():
                actual_file_path.unlink()
                logger.debug(f"Cleaned up temporary file: {actual_file_path}")
            
            return processing_info
            
        except Exception as e:
            error_info = {
                'file_path': str(file_path),
                'file_type': self.get_file_type(file_path),
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'success': False,
                'error': str(e),
                'doc_object': None,
                'result_object': None
            }
            
            logger.error(f"Failed to process {file_path}: {e}")
            self.stats['errors'].append(error_info)
            
            # Cleanup temporary file if created
            if 'temp_file_created' in locals() and temp_file_created and 'actual_file_path' in locals() and actual_file_path.exists():
                actual_file_path.unlink()
                logger.debug(f"Cleaned up temporary file after error: {actual_file_path}")
            
            return error_info
    
    def extract_images_from_document(self, doc, file_stem: str, doc_output_dir: Path = None, source_doc=None) -> List[Dict[str, Any]]:
        """
        Extract images from a processed Docling document with size filtering.
        
        Based on debug output:
        - doc.pages is a dict with 16 items, not a list
        - doc.pictures is a list with 14 items (PictureItem objects)
        - Each picture has attributes like get_image(), caption, bbox, page_no
        
        Args:
            doc: DoclingDocument object from docling_core.types.doc.document
            file_stem: Base name for output files
            doc_output_dir: Optional specific directory for this document
            source_doc: Source document for high-resolution image extraction
            
        Returns:
            List of extracted image information with size filtering applied
        """
        extracted_images = []
        
        # First try to extract HIGH-RESOLUTION page images (from generate_page_images=True)
        page_images_extracted = False
        if hasattr(doc, 'pages') and doc.pages:
            # Pages is a dict - iterate over sorted keys
            page_keys = sorted(doc.pages.keys())
            for page_key in page_keys:
                page = doc.pages[page_key]
                if hasattr(page, 'image') and page.image:
                    try:
                        page_image_path = doc_output_dir / f"page_{page_key:03d}_full.png"
                        
                        # Convert ImageRef to PIL Image if needed
                        page_image_data = page.image
                        pil_image = None
                        
                        # Handle ImageRef objects (from Docling with generate_page_images=True)
                        if hasattr(page_image_data, 'uri') and str(page_image_data.uri).startswith('data:'):
                            # Extract base64 data from data URI
                            import base64
                            data_uri = str(page_image_data.uri)
                            
                            # Parse data URI format: data:image/png;base64,<base64_data>
                            header, base64_data = data_uri.split(',', 1)
                            image_bytes = base64.b64decode(base64_data)
                            
                            # Convert to PIL Image
                            pil_image = Image.open(BytesIO(image_bytes))
                        
                        # Handle PIL Images directly
                        elif isinstance(page_image_data, Image.Image):
                            pil_image = page_image_data
                        elif hasattr(page_image_data, 'save'):  # Check if it has save method
                            pil_image = page_image_data
                        
                        # Save the PIL image
                        if pil_image:
                            pil_image.save(page_image_path, "PNG", optimize=False, compress_level=1)
                            
                            extracted_images.append({
                                'index': f"page_{page_key}",
                                'type': 'full_page',
                                'page_no': page_key,
                                'saved_path': str(page_image_path),
                                'caption': f"Full page {page_key + 1}"
                            })
                            page_images_extracted = True
                            logger.debug(f"Extracted full page {page_key} image")
                        else:
                            logger.warning(f"Could not convert page {page_key} image to PIL Image")
                            
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_key} image: {e}")
        
        # Extract images from pictures list (main source based on debug output)
        images_source = None
        if hasattr(doc, 'pictures') and doc.pictures:
            images_source = doc.pictures
            logger.debug(f"Found {len(doc.pictures)} pictures in doc.pictures")
        elif hasattr(doc, 'images') and doc.images:
            # Fallback for older versions or different structures
            images_source = doc.images
            logger.debug(f"Found {len(doc.images)} images in doc.images")
        else:
            # Try to find images in document elements (pages is dict)
            images_in_elements = []
            if hasattr(doc, 'pages') and doc.pages:
                for page_key, page in doc.pages.items():
                    if hasattr(page, 'elements') and page.elements:
                        for element in page.elements:
                            if (hasattr(element, 'label') and element.label == "Picture" and 
                                hasattr(element, 'image')):
                                images_in_elements.append(element)
            if images_in_elements:
                images_source = images_in_elements
                logger.debug(f"Found {len(images_in_elements)} images in page elements")
        
        if not images_source:
            if not page_images_extracted:
                logger.debug("No images found in document")
            return extracted_images
        
        # Use document's output directory if provided, otherwise fallback to images subfolder
        if doc_output_dir:
            images_dir = doc_output_dir
        else:
            images_dir = self.output_dir / "images" / file_stem
        images_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create progress bar for image extraction
            with tqdm(images_source, desc="Extracting images", unit="image", leave=False) as pbar:
                for idx, picture in enumerate(pbar):
                    # Update progress bar description
                    pbar.set_description(f"Processing image {idx + 1}")
                    
                    image_info = {
                        'index': idx,
                        'type': 'extracted_picture',
                        'caption': getattr(picture, 'caption', ''),
                        'bbox': getattr(picture, 'bbox', None),
                        'page_no': getattr(picture, 'page_no', None)
                    }
                    
                    # Save the image if available - try different image access methods
                    image_data = None
                    
                    # First try the get_image() method with source document for HIGH RESOLUTION
                    if hasattr(picture, 'get_image') and source_doc:
                        try:
                            image_data = picture.get_image(source_doc)
                            logger.debug(f"Got image using get_image(): {type(image_data)}")
                        except Exception as e:
                            logger.warning(f"Failed to get image using get_image(): {e}")
                    
                    # Fallback to direct image access
                    if image_data is None and hasattr(picture, 'image') and picture.image:
                        image_data = picture.image
                    elif image_data is None and hasattr(picture, 'pil_image') and picture.pil_image:
                        image_data = picture.pil_image
                    elif image_data is None and hasattr(picture, 'data') and picture.data:
                        image_data = picture.data
                    
                    if image_data:
                        try:
                            # First, get the PIL Image object for size checking
                            pil_image = None
                            
                            # Handle ImageRef objects (from Docling with generate_picture_images=True)
                            if hasattr(image_data, 'uri') and str(image_data.uri).startswith('data:'):
                                # Extract base64 data from data URI
                                import base64
                                data_uri = str(image_data.uri)
                                
                                # Parse data URI format: data:image/png;base64,<base64_data>
                                header, base64_data = data_uri.split(',', 1)
                                image_bytes = base64.b64decode(base64_data)
                                
                                # Convert to PIL Image
                                pil_image = Image.open(BytesIO(image_bytes))
                                
                            # Handle PIL Images
                            elif isinstance(image_data, Image.Image):
                                pil_image = image_data
                            elif hasattr(image_data, 'save'):  # Check if it has save method
                                pil_image = image_data
                            else:
                                # Try to handle other image formats
                                try:
                                    pil_image = Image.fromarray(image_data)
                                except:
                                    # Last resort - try to convert bytes to PIL
                                    pil_image = Image.open(BytesIO(image_data))
                            
                            if pil_image:
                                # CHECK IMAGE SIZE - FILTER OUT SMALL ICONS
                                width, height = pil_image.size
                                area = width * height
                                
                                # Apply size filters to remove small icons and low-quality images
                                if (width >= self.config.min_image_width and 
                                    height >= self.config.min_image_height and 
                                    area >= self.config.min_image_area):
                                    
                                    # Image passes size requirements - save it
                                    image_path = images_dir / f"image_{idx:03d}.png"
                                    pil_image.save(image_path, "PNG", optimize=False, compress_level=1)
                                    
                                    image_info['saved_path'] = str(image_path)
                                    image_info['width'] = width
                                    image_info['height'] = height
                                    image_info['area'] = area
                                    
                                    # Update progress bar with success
                                    pbar.set_postfix({
                                        'Saved': f'{width}x{height}',
                                        'Area': f'{area}'
                                    })
                                    logger.debug(f"Saved image {idx} ({width}x{height}) to {image_path}")
                                    
                                else:
                                    # Image too small - skip it
                                    image_info['skipped_reason'] = f"Image too small ({width}x{height}, area={area})"
                                    image_info['width'] = width
                                    image_info['height'] = height
                                    image_info['area'] = area
                                    
                                    # Update progress bar with skip info
                                    pbar.set_postfix({
                                        'Skipped': f'{width}x{height}',
                                        'Reason': 'Too small'
                                    })
                                    logger.debug(f"Skipped small image {idx}: {width}x{height} (area={area})")
                            else:
                                image_info['skip_reason'] = "Could not convert to PIL Image"
                                pbar.set_postfix({'Error': 'Invalid image'})
                            
                        except Exception as e:
                            logger.warning(f"Failed to process image {idx}: {e}")
                            image_info['save_error'] = str(e)
                            pbar.set_postfix({'Error': str(e)[:20]})
                    else:
                        logger.warning(f"No image data found for picture {idx}")
                        pbar.set_postfix({'Warning': 'No image data'})
                    
                    extracted_images.append(image_info)
        
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
        
        return extracted_images
    
    def extract_tables_from_document(self, doc, file_stem: str, doc_output_dir: Path = None) -> List[Dict[str, Any]]:
        """
        Extract tables from a processed Docling document.
        
        Based on debug output:
        - doc.tables is a list with 12 items (TableItem objects)
        - Each table has attributes like caption, bbox, page_no, export_to_* methods
        
        Args:
            doc: DoclingDocument object from docling_core.types.doc.document
            file_stem: Base name for output files
            doc_output_dir: Optional specific directory for this document
            
        Returns:
            List of extracted table information
        """
        extracted_tables = []
        
        # Check if document has tables (should be a list based on debug output)
        if not (hasattr(doc, 'tables') and doc.tables):
            logger.debug("No tables found in document")
            return extracted_tables
        
        logger.debug(f"Found {len(doc.tables)} tables to extract")
        
        # Use document's output directory if provided, otherwise fallback to tables subfolder  
        if doc_output_dir:
            tables_dir = doc_output_dir
        else:
            tables_dir = self.output_dir / "tables" / file_stem
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create progress bar for table extraction
            with tqdm(doc.tables, desc="Extracting tables", unit="table", leave=False) as pbar:
                for idx, table in enumerate(pbar):
                    # Update progress bar description
                    pbar.set_description(f"Processing table {idx + 1}")
                    
                    table_info = {
                        'index': idx,
                        'type': 'extracted_table',
                        'caption': getattr(table, 'caption', ''),
                        'bbox': getattr(table, 'bbox', None),
                        'page_no': getattr(table, 'page_no', None),
                        'rows': getattr(table, 'num_rows', None),
                        'cols': getattr(table, 'num_cols', None)
                    }
                    
                    # Export table data
                    try:
                        formats_saved = []
                        
                        # Save as CSV if data is available
                        if hasattr(table, 'export_to_dataframe'):
                            df = table.export_to_dataframe()
                            csv_path = tables_dir / f"table_{idx:03d}.csv"
                            df.to_csv(csv_path, index=False)
                            table_info['csv_path'] = str(csv_path)
                            formats_saved.append('CSV')
                        
                        # Save as markdown
                        if hasattr(table, 'export_to_markdown'):
                            md_content = table.export_to_markdown()
                            md_path = tables_dir / f"table_{idx:03d}.md"
                            md_path.write_text(md_content, encoding='utf-8')
                            table_info['markdown_path'] = str(md_path)
                            formats_saved.append('MD')
                        
                        # # Save table image if available
                        # if hasattr(table, 'image') and table.image:
                        #     img_path = tables_dir / f"table_{idx:03d}.png"
                        #     if isinstance(table.image, Image.Image):
                        #         table.image.save(img_path)
                        #     table_info['image_path'] = str(img_path)
                        #     formats_saved.append('PNG')
                        
                        # Update progress bar with success info
                        pbar.set_postfix({
                            'Formats': '+'.join(formats_saved) if formats_saved else 'None',
                            'Rows': table_info.get('rows', '?'),
                            'Cols': table_info.get('cols', '?')
                        })
                        
                        logger.debug(f"Saved table {idx} data")
                        
                    except Exception as e:
                        logger.warning(f"Failed to save table {idx}: {e}")
                        table_info['save_error'] = str(e)
                        pbar.set_postfix({'Error': str(e)[:20]})
                    
                    extracted_tables.append(table_info)
        
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
        
        return extracted_tables
    
    def _get_document_origin_info(self, doc) -> Dict[str, Any]:
        """
        Extract document origin information from Docling document.
        
        Based on debug output, origin has: filename, mimetype, binary_hash attributes.
        
        Args:
            doc: DoclingDocument object
            
        Returns:
            Dictionary with origin information
        """
        origin_info = {
            'filename': '',
            'mimetype': '',
            'binary_hash': ''
        }
        
        if hasattr(doc, 'origin') and doc.origin:
            origin = doc.origin
            # Use exact attributes found in debug output
            origin_info['filename'] = getattr(origin, 'filename', '')
            origin_info['mimetype'] = getattr(origin, 'mimetype', '')
            origin_info['binary_hash'] = getattr(origin, 'binary_hash', '')
            
        return origin_info
    
    def _get_document_title(self, doc, file_path: Path) -> str:
        """
        Extract document title from Docling document.
        
        Based on debug output, doc has a 'name' attribute (length 89).
        Fallback to first meaningful text or filename.
        
        Args:
            doc: DoclingDocument object
            file_path: Original file path
            
        Returns:
            Document title string
        """
        # First try the name attribute (found in debug output)
        if hasattr(doc, 'name') and doc.name:
            doc_name = str(doc.name).strip()
            if doc_name and doc_name != file_path.stem:
                return doc_name
        
        # Fallback: try to find title from texts list (found 900 text items in debug)
        if hasattr(doc, 'texts') and doc.texts:
            try:
                for text_item in doc.texts[:10]:  # Check first 10 text items
                    if hasattr(text_item, 'text') and text_item.text:
                        text_content = str(text_item.text).strip()
                        # Look for title-like text (short, not abstract/introduction)
                        if (50 < len(text_content) < 200 and 
                            not any(word in text_content.lower() for word in 
                                   ['abstract', 'introduction', 'figure', 'table', 'page'])):
                            return text_content
            except Exception as e:
                logger.debug(f"Error extracting title from texts: {e}")
        
        # Ultimate fallback: use filename without extension
        return file_path.stem
    
    def _get_document_content_stats(self, doc) -> Dict[str, Any]:
        """
        Extract content statistics from Docling document.
        
        Based on debug output:
        - pages: dict with 16 items
        - pictures: list with 14 items  
        - tables: list with 12 items
        - texts: list with 900 items
        
        Args:
            doc: DoclingDocument object
            
        Returns:
            Dictionary with content statistics
        """
        stats = {
            'total_pages': 0,
            'total_images': 0,
            'total_tables': 0,
            'total_texts': 0,
            'total_text_length': 0
        }
        
        # Pages count - pages is a dict, not list
        if hasattr(doc, 'pages') and doc.pages:
            stats['total_pages'] = len(doc.pages)
        
        # Pictures count - pictures is a list
        if hasattr(doc, 'pictures') and doc.pictures:
            stats['total_images'] = len(doc.pictures)
        
        # Tables count - tables is a list
        if hasattr(doc, 'tables') and doc.tables:
            stats['total_tables'] = len(doc.tables)
        
        # Texts count - texts is a list
        if hasattr(doc, 'texts') and doc.texts:
            stats['total_texts'] = len(doc.texts)
        
        # Calculate total text length using export_to_markdown method
        try:
            if hasattr(doc, 'export_to_markdown'):
                markdown_text = doc.export_to_markdown()
                stats['total_text_length'] = len(markdown_text)
            else:
                logger.warning("Document does not have export_to_markdown method")
        except Exception as e:
            logger.warning(f"Failed to export markdown: {e}")
            # Fallback: sum text from texts list
            if hasattr(doc, 'texts') and doc.texts:
                total_length = 0
                for text_item in doc.texts:
                    if hasattr(text_item, 'text') and text_item.text:
                        total_length += len(str(text_item.text))
                stats['total_text_length'] = total_length
        
        return stats
    
    def _get_document_pages_info(self, doc) -> List[Dict[str, Any]]:
        """
        Extract detailed page information from Docling document.
        
        Based on debug output, pages is a dict (not list) with page numbers as keys.
        
        Args:
            doc: DoclingDocument object
            
        Returns:
            List of page information dictionaries
        """
        pages_info = []
        
        if not (hasattr(doc, 'pages') and doc.pages):
            return pages_info
        
        # Pages is a dict - get sorted keys for proper page order
        try:
            page_keys = sorted(doc.pages.keys())
            
            # Create progress bar for pages processing
            with tqdm(page_keys, desc="Processing pages", unit="page", leave=False) as pbar:
                for page_key in pbar:
                    # Update progress bar description
                    pbar.set_description(f"Processing page {page_key + 1}" if isinstance(page_key, int) else f"Processing page {page_key}")
                    page = doc.pages[page_key]
                    
                    page_data = {
                        'page_number': int(page_key) + 1 if isinstance(page_key, int) else page_key,
                        'page_key': page_key,
                        'dimensions': None,
                        'elements_count': 0,
                        'has_content': False,
                        'elements_by_type': {}
                    }
                    
                    # Check for page dimensions
                    if hasattr(page, 'size') and page.size:
                        if hasattr(page.size, 'width') and hasattr(page.size, 'height'):
                            page_data['dimensions'] = {
                                'width': float(page.size.width),
                                'height': float(page.size.height)
                            }
                    
                    # Count elements on this page by checking provenance in pictures, tables, texts
                    page_num = page_data['page_number']
                    images_on_page = 0
                    tables_on_page = 0
                    texts_on_page = 0
                    
                    # Count pictures on this page
                    if hasattr(doc, 'pictures') and doc.pictures:
                        for picture in doc.pictures:
                            if hasattr(picture, 'prov') and picture.prov:
                                prov = picture.prov[0] if isinstance(picture.prov, list) else picture.prov
                                if getattr(prov, 'page_no', None) == page_num:
                                    images_on_page += 1
                    
                    # Count tables on this page
                    if hasattr(doc, 'tables') and doc.tables:
                        for table in doc.tables:
                            if hasattr(table, 'prov') and table.prov:
                                prov = table.prov[0] if isinstance(table.prov, list) else table.prov
                                if getattr(prov, 'page_no', None) == page_num:
                                    tables_on_page += 1
                    
                    # Count texts on this page
                    if hasattr(doc, 'texts') and doc.texts:
                        for text in doc.texts:
                            if hasattr(text, 'prov') and text.prov:
                                prov = text.prov[0] if isinstance(text.prov, list) else text.prov
                                if getattr(prov, 'page_no', None) == page_num:
                                    texts_on_page += 1
                    
                    # Update page data
                    page_data['elements_count'] = images_on_page + tables_on_page + texts_on_page
                    page_data['has_content'] = page_data['elements_count'] > 0
                    
                    # Set elements by type (this replaces individual count fields)
                    page_data['elements_by_type'] = {}
                    if images_on_page >= 0:
                        page_data['elements_by_type']['pictures'] = images_on_page
                    if tables_on_page >= 0:
                        page_data['elements_by_type']['tables'] = tables_on_page
                    if texts_on_page >= 0:
                        page_data['elements_by_type']['texts'] = texts_on_page
                    
                    # Check for other content indicators
                    if not page_data['has_content']:
                        # Check if page has any content attributes
                        content_attrs = ['text', 'items', 'content']
                        for attr in content_attrs:
                            if hasattr(page, attr) and getattr(page, attr):
                                page_data['has_content'] = True
                                break
                    
                    # Update progress bar with detailed info
                    pbar.set_postfix({
                        'Elements': page_data['elements_count'],
                        'Images': images_on_page,
                        'Tables': tables_on_page,
                        'Content': 'Yes' if page_data['has_content'] else 'No'
                    })
                    
                    pages_info.append(page_data)
                
        except Exception as e:
            logger.error(f"Error processing pages info: {e}")
            # Fallback: just count pages
            pages_info = [
                {
                    'page_number': i + 1,
                    'page_key': i,
                    'dimensions': None,
                    'elements_count': 0,
                    'has_content': False,
                    'elements_by_type': {}
                }
                for i in range(len(doc.pages))
            ]
        
        return pages_info
    
    def _get_detailed_images_metadata(self, doc) -> List[Dict[str, Any]]:
        """Extract detailed metadata for each image including location and page info."""
        images_metadata = []
        
        try:
            if hasattr(doc, 'pictures') and doc.pictures:
                for idx, picture in enumerate(doc.pictures):
                    image_info = {
                        'index': idx,
                        'id': getattr(picture, 'id', f'image_{idx:03d}'),
                        'type': 'picture',
                        'label': getattr(picture, 'label', 'picture'),
                        'caption': getattr(picture, 'caption', ''),
                    }
                    
                    # Extract VLM description from annotations
                    vlm_description = ''
                    vlm_model = ''
                    picture_classification = {}
                    
                    if hasattr(picture, 'annotations') and picture.annotations:
                        for annotation in picture.annotations:
                            # Extract VLM image description
                            if (hasattr(annotation, 'kind') and annotation.kind == 'description' and
                                hasattr(annotation, 'text') and annotation.text):
                                vlm_description = annotation.text
                                if hasattr(annotation, 'provenance'):
                                    vlm_model = annotation.provenance
                            
                            # Extract picture classification
                            elif (hasattr(annotation, 'kind') and annotation.kind == 'classification' and
                                  hasattr(annotation, 'predicted_classes')):
                                picture_classification = {
                                    'top_class': annotation.predicted_classes[0].class_name if annotation.predicted_classes else 'unknown',
                                    'confidence': annotation.predicted_classes[0].confidence if annotation.predicted_classes else 0.0,
                                    'classifier': getattr(annotation, 'provenance', 'unknown')
                                }
                    
                    # Use VLM description as caption if available, fallback to original caption
                    if vlm_description:
                        image_info['caption'] = vlm_description
                        image_info['vlm_description'] = vlm_description
                        image_info['vlm_model'] = vlm_model
                        image_info['has_vlm_description'] = True
                    else:
                        image_info['vlm_description'] = ''
                        image_info['vlm_model'] = ''
                        image_info['has_vlm_description'] = False
                    
                    # Add picture classification info
                    image_info['classification'] = picture_classification
                    
                    # Extract spatial information from provenance
                    if hasattr(picture, 'prov') and picture.prov:
                        prov = picture.prov[0] if isinstance(picture.prov, list) else picture.prov
                        
                        # Page number
                        image_info['page_number'] = getattr(prov, 'page_no', None)
                        
                        # Bounding box coordinates
                        if hasattr(prov, 'bbox') and prov.bbox:
                            bbox = prov.bbox
                            image_info['bbox'] = {
                                'x1': getattr(bbox, 'l', None),  # left
                                'y1': getattr(bbox, 't', None),  # top
                                'x2': getattr(bbox, 'r', None),  # right
                                'y2': getattr(bbox, 'b', None),  # bottom
                            }
                            
                            # Calculate dimensions and area
                            if all(v is not None for v in image_info['bbox'].values()):
                                width = abs(image_info['bbox']['x2'] - image_info['bbox']['x1'])
                                height = abs(image_info['bbox']['y2'] - image_info['bbox']['y1'])
                                image_info['dimensions'] = {
                                    'width': round(width, 2),
                                    'height': round(height, 2)
                                }
                                image_info['area'] = round(width * height, 2)
                            
                            # Coordinate origin information
                            if hasattr(bbox, 'coord_origin'):
                                image_info['coordinate_origin'] = str(bbox.coord_origin)
                    
                    images_metadata.append(image_info)
        
        except Exception as e:
            logger.warning(f"Error extracting detailed image metadata: {e}")
        
        return images_metadata
    
    def _get_detailed_tables_metadata(self, doc) -> List[Dict[str, Any]]:
        """Extract detailed metadata for each table including location and basic structure info."""
        tables_metadata = []
        
        try:
            if hasattr(doc, 'tables') and doc.tables:
                for idx, table in enumerate(doc.tables):
                    table_info = {
                        'index': idx,
                        'id': getattr(table, 'id', f'table_{idx:03d}'),
                        'type': 'table',
                        'label': getattr(table, 'label', 'table'),
                        'caption': getattr(table, 'caption', ''),
                    }
                    
                    # Extract spatial information from provenance (same as images)
                    if hasattr(table, 'prov') and table.prov:
                        prov = table.prov[0] if isinstance(table.prov, list) else table.prov
                        
                        # Page number
                        table_info['page_number'] = getattr(prov, 'page_no', None)
                        
                        # Bounding box coordinates
                        if hasattr(prov, 'bbox') and prov.bbox:
                            bbox = prov.bbox
                            table_info['bbox'] = {
                                'x1': getattr(bbox, 'l', None),  # left
                                'y1': getattr(bbox, 't', None),  # top
                                'x2': getattr(bbox, 'r', None),  # right
                                'y2': getattr(bbox, 'b', None),  # bottom
                            }
                            
                            # Calculate dimensions and area
                            if all(v is not None for v in table_info['bbox'].values()):
                                width = abs(table_info['bbox']['x2'] - table_info['bbox']['x1'])
                                height = abs(table_info['bbox']['y2'] - table_info['bbox']['y1'])
                                table_info['dimensions'] = {
                                    'width': round(width, 2),
                                    'height': round(height, 2)
                                }
                                table_info['area'] = round(width * height, 2)
                            
                            # Coordinate origin information
                            if hasattr(bbox, 'coord_origin'):
                                table_info['coordinate_origin'] = str(bbox.coord_origin)
                    
                    # Extract basic table structure information (no preview data)
                    try:
                        if hasattr(table, 'export_to_dataframe'):
                            df = table.export_to_dataframe()
                            if df is not None and not df.empty:
                                table_info['structure'] = {
                                    'rows': len(df),
                                    'columns': len(df.columns),
                                    'column_names': df.columns.tolist(),
                                    'has_data': True
                                }
                            else:
                                table_info['structure'] = {
                                    'rows': 0,
                                    'columns': 0,
                                    'has_data': False
                                }
                    except Exception as e:
                        logger.debug(f"Error extracting table structure for table {idx}: {e}")
                        table_info['structure'] = {'error': 'Could not analyze structure'}
                    
                    tables_metadata.append(table_info)
        
        except Exception as e:
            logger.warning(f"Error extracting detailed table metadata: {e}")
        
        return tables_metadata
    
    def extract_metadata_from_document(self, doc, result, file_path: Path) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a processed Docling document.
        
        Uses the actual document structure discovered through debugging:
        - DoclingDocument from docling_core.types.doc.document
        - Has attributes: name, version, origin, pages (dict), pictures (list), tables (list), texts (list)
        - Origin has: filename, mimetype, binary_hash
        - Pages is a dict with page numbers as keys, not a list
        
        Args:
            doc: DoclingDocument object from docling_core.types.doc.document
            result: Conversion result object (not used in current implementation)
            file_path: Original file path
            
        Returns:
            Dictionary containing comprehensive document metadata
        """
        logger.debug(f"Extracting metadata from document type: {type(doc)}")
        
        # Get Docling version from document or module
        docling_version = 'unknown'
        if hasattr(doc, 'version') and doc.version:
            docling_version = str(doc.version)
        else:
            try:
                import docling
                docling_version = getattr(docling, '__version__', 'unknown')
            except ImportError:
                pass
        
        # Build metadata using dedicated helper methods
        metadata = {
            'file_info': {
                'name': file_path.name,
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'type': self.get_file_type(file_path),
                'modified': file_path.stat().st_mtime
            },
            'document_info': {
                'title': self._get_document_title(doc, file_path),
                'docling_version': docling_version,
                **self._get_document_origin_info(doc)
            },
            'content_stats': self._get_document_content_stats(doc),
            'processing_info': {
                'processor_version': 'MultimodalDocumentProcessor-v1.0',  # Updated class name
                'docling_version': docling_version,
                'processing_timestamp': datetime.now().isoformat(),
                'gpu_used': self.config.use_gpu and torch.cuda.is_available(),
                'ocr_enabled': self.config.enable_ocr,
                'vlm_enabled': self.config.enable_vlm,
                'asr_enabled': self.config.enable_asr,
                'image_filtering': {
                    'min_width': self.config.min_image_width,
                    'min_height': self.config.min_image_height,
                    'min_area': self.config.min_image_area
                }
            },
            'pages': self._get_document_pages_info(doc),
            'images_details': self._get_detailed_images_metadata(doc),
            'tables_details': self._get_detailed_tables_metadata(doc)
        }
        
        logger.debug(f"Extracted metadata with {len(metadata['pages'])} pages, "
                    f"{metadata['content_stats']['total_images']} images, "
                    f"{metadata['content_stats']['total_tables']} tables")
        
        return metadata
    
    def _get_safe_output_path(self, filename: str, max_length: int = 50) -> str:
        """
        Get a safe output directory name by truncating long filenames.
        
        Args:
            filename: Original filename stem
            max_length: Maximum length (default 50 for Windows paths)
            
        Returns:
            Safe directory name
        """
        filename = sanitize_filename_stem(filename)
        if len(filename) <= max_length:
            return filename
        
        import hashlib
        hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
        truncated = filename[:max_length - 9]
        return f"{truncated}_{hash_suffix}"
    
    def export_processed_document(self, processing_info: Dict[str, Any]) -> Dict[str, str]:
        """
        Export processed document to various formats.
        
        Args:
            processing_info: Processing information from process_single_file
            
            ```
            {
                'file_path': str,
                'file_size': int,
                'file_type': str,
                'processing_time': float,
                'pages': int,
                'success': bool,
                'doc_object': DoclingDocument or None,
                'result_object': ConversionResult or None,
                'error': str or None
            }
            
        Returns:
            Dictionary with paths to exported files
        """
        if not processing_info['success']:
            return {}
        
        doc = processing_info['doc_object']
        result = processing_info['result_object']
        file_path = Path(processing_info['file_path'])
        file_stem = file_path.stem
        
        # Use safe filename for output directory (truncate if too long to avoid Windows 260 char path limit)
        # This matches the safe_stem used in normalizer.py
        safe_stem = self._get_safe_output_path(file_stem)
        
        exported_files = {}
        
        try:
            # Create simple document-specific output directory: output_dir/filename/
            doc_output_dir = self.output_dir / safe_stem
            doc_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Export ONLY to Markdown (main content)
            try:
                markdown_content = doc.export_to_markdown()
                markdown_path = doc_output_dir / f"{safe_stem}.md"
                markdown_path.write_text(markdown_content, encoding='utf-8')
                exported_files['markdown'] = str(markdown_path)
                logger.debug(f"Exported markdown to {markdown_path}")
            except Exception as e:
                logger.warning(f"Failed to export markdown: {e}")
            
            # Extract and save images to the same folder
            if self.config.export_images:
                extracted_images = self.extract_images_from_document(doc, safe_stem, doc_output_dir, doc)
                if extracted_images:
                    exported_files['images'] = extracted_images
                    logger.debug(f"Extracted {len(extracted_images)} images")
            
            # Extract and save tables to the same folder
            if self.config.export_tables:
                extracted_tables = self.extract_tables_from_document(doc, safe_stem, doc_output_dir)
                if extracted_tables:
                    exported_files['tables'] = extracted_tables
                    logger.debug(f"Extracted {len(extracted_tables)} tables")
            
            # Save metadata to the same folder
            if self.config.export_metadata:
                metadata = self.extract_metadata_from_document(doc, result, file_path)
                metadata_path = doc_output_dir / f"{safe_stem}_metadata.json"
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
                
                exported_files['metadata'] = str(metadata_path)
                logger.debug(f"Saved metadata to {metadata_path}")
            
            logger.info(f"Successfully exported {safe_stem} to {len(exported_files)} formats")
            
        except Exception as e:
            logger.error(f"Error exporting document {safe_stem}: {e}")
        
        return exported_files
    
    def process_batch(self, file_paths: List[Path] = None) -> Dict[str, Any]:
        """
        Process multiple files in batch.
        
        Args:
            file_paths: List of file paths to process. If None, scans input directory.
            
        Returns:
            Dictionary containing batch processing results
        """
        if file_paths is None:
            file_paths = self.scan_input_directory()
        
        if not file_paths:
            logger.warning("No files found to process")
            return {'success': False, 'message': 'No files found'}
        
        batch_start_time = datetime.now()
        batch_results = {
            'total_files': len(file_paths),
            'processed_files': 0,
            'failed_files': 0,
            'processing_time': 0,
            'results': [],
            'errors': [],
            'exported_files': {}
        }
        
        logger.info(f"Starting batch processing of {len(file_paths)} files")
        
        # Create progress bar for batch processing
        with tqdm(file_paths, desc="Processing documents", unit="file") as pbar:
            for idx, file_path in enumerate(pbar, 1):
                # Update progress bar description with current file
                pbar.set_description(f"Processing {file_path.name}")
                
                logger.info(f"Processing file {idx}/{len(file_paths)}: {file_path.name}")
                
                # Process single file. Return values:
                # {
                #     'file_path': str,
                #     'file_size': int,
                #     'file_type': str,
                #     'processing_time': float,
                #     'pages': int,
                #     'success': bool,
                #     'doc_object': DoclingDocument or None,
                #     'result_object': ConversionResult or None,
                #     'error': str or None
                # }
                processing_info = self.process_single_file(file_path)
                
                if processing_info['success']:
                    # Export the processed document
                    exported_files = self.export_processed_document(processing_info)
                    processing_info['exported_files'] = exported_files
                    
                    batch_results['processed_files'] += 1
                    batch_results['results'].append(processing_info)
                    
                    # Update statistics
                    self.stats['processed_files'] += 1
                    
                    # Update progress bar postfix with success info
                    pbar.set_postfix({
                        'Success': batch_results['processed_files'],
                        'Failed': batch_results['failed_files'],
                        'Current': f"{processing_info.get('processing_time', 0):.1f}s"
                    })
                    
                else:
                    batch_results['failed_files'] += 1
                    batch_results['errors'].append(processing_info)
                    
                    # Update progress bar postfix with error info
                    pbar.set_postfix({
                        'Success': batch_results['processed_files'],
                        'Failed': batch_results['failed_files'],
                        'Error': processing_info.get('error', 'Unknown')[:20]
                    })
                self.stats['failed_files'] += 1
        
        # Calculate total processing time
        batch_end_time = datetime.now()
        batch_results['processing_time'] = (batch_end_time - batch_start_time).total_seconds()
        self.stats['processing_time'] = batch_results['processing_time']
        
        # Log summary
        logger.info(f"Batch processing completed in {batch_results['processing_time']:.2f}s")
        logger.info(f"Successfully processed: {batch_results['processed_files']} files")
        logger.info(f"Failed to process: {batch_results['failed_files']} files")
        
        # Save batch summary
        self._save_batch_summary(batch_results)
        
        return batch_results
    
    def _save_batch_summary(self, batch_results: Dict[str, Any]) -> None:
        """Save batch processing summary to output directory."""
        try:
            summary_path = self.output_dir / "logs" / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Prepare summary (exclude heavy objects for JSON serialization)
            summary = {
                'batch_info': {
                    'total_files': batch_results['total_files'],
                    'processed_files': batch_results['processed_files'],
                    'failed_files': batch_results['failed_files'],
                    'processing_time': batch_results['processing_time'],
                    'success_rate': batch_results['processed_files'] / batch_results['total_files'] * 100
                },
                'file_results': [
                    {
                        'file_path': r['file_path'],
                        'success': r['success'],
                        'processing_time': r['processing_time'],
                        'file_type': r['file_type'],
                        'exported_formats': list(r.get('exported_files', {}).keys()) if r['success'] else []
                    }
                    for r in batch_results['results'] + batch_results['errors']
                ],
                'statistics': self.stats,
                'configuration': {
                    'gpu_enabled': self.config.use_gpu,
                    'ocr_enabled': self.config.enable_ocr,
                    'vlm_enabled': self.config.enable_vlm,
                    'asr_enabled': self.config.enable_asr
                }
            }
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Batch summary saved to {summary_path}")
            
        except Exception as e:
            logger.error(f"Failed to save batch summary: {e}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary containing processing statistics
        """
        return self.stats.copy()
    
    def cleanup_temp_files(self) -> None:
        """Clean up any temporary files created during processing."""
        try:
            # Add cleanup logic here if needed
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_temp_files()


"""
EXAMPLE USAGES
==============

## Basic Usage

```python
from src.document_processor import MultimodalDocumentProcessor, ProcessingConfig

# Quick setup
config = ProcessingConfig(enable_ocr=True, enable_vlm=True, export_metadata=True)
processor = MultimodalDocumentProcessor('input', 'output', config)

# Process single file
result = processor.process_single_file('document.pdf')
if result['success']:
    exported = processor.export_processed_document(result)
    print(f"Exported: {list(exported.keys())}")

# Batch processing
batch_results = processor.process_batch()
print(f"Processed: {batch_results['processed_files']}/{batch_results['total_files']} files")
```

## Configuration Examples

```python
# Research documents (high quality)
research_config = ProcessingConfig(
    enable_ocr=True, ocr_engine='tesseract', 
    min_image_area=50000, export_images=True
)

# Fast bulk processing
bulk_config = ProcessingConfig(
    enable_ocr=True, enable_vlm=False, 
    ocr_engine='rapidocr', export_images=False
)

# Multimedia content
multimedia_config = ProcessingConfig(
    enable_ocr=True, enable_vlm=True, enable_asr=True,
    export_images=True, export_tables=True
)
```

## Metadata Access

```python
# Access comprehensive metadata
import json
with open(exported['metadata'], 'r') as f:
    metadata = json.load(f)

print(f"Pages: {metadata['content_stats']['total_pages']}")
print(f"Images: {metadata['content_stats']['total_images']}")

# Image locations
for img in metadata['images_details']:
    bbox = img['bbox']
    print(f"Image {img['index']} on page {img['page_number']}: "
          f"({bbox['x1']}, {bbox['y1']}) to ({bbox['x2']}, {bbox['y2']})")
```

## Output Structure
```
output/
├── document_name/
│   ├── document_name.md          # Main content
│   ├── document_name_metadata.json  # Spatial info & stats
│   ├── image_001.png             # Extracted images
│   └── table_001.csv             # Extracted tables
└── logs/
    └── processing_20251024.log
```

Supports: PDF, DOCX, PPTX, XLSX, images, audio, HTML, Markdown
Features: OCR, VLM, ASR, spatial metadata, batch processing, GPU acceleration
"""
