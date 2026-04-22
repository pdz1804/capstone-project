"""Unified smart-router document processor (V2).

Dispatches each file to its optimal reader, normalises all outputs to the
same schema, and falls back to Docling when no custom reader is available
or when one fails.

Routing logic:
  .docx / .doc     -> docx_reader_v2  (DocxParser)
  .xlsx / .xls / .xlsm -> xlsx_reader_v2  (process_excel_file)
  .pptx / .ppt     -> pptx_reader     (PptxParser)
  .pdf              -> pdf_reader      (CustomPdfReader + ItemSequencer)
  everything else   -> Docling         (identical to document_processor.py)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.processor.utils import sanitize_filename_stem

logger = logging.getLogger(__name__)

# Module-level import guard for pptx_reader (has `app.*` FE imports)
PPTX_READER_AVAILABLE: bool = False
try:
    from .pptx_reader import PptxParser  # noqa: F401
    PPTX_READER_AVAILABLE = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ProcessingConfigV2:
    """Configuration for the unified V2 document processor.

    Does NOT subclass ProcessingConfig -- wraps it by composition.
    """

    prefer_custom_readers: bool = True
    excel_reader_mode: str = "xml"  # "xml" | "docling"
    pptx_llm_validate_headers: bool = False
    # PDF content source for CustomPdfReader: "pymupdf" | "docling" | "hybrid"
    pdf_content_source: str = "hybrid"
    docling_config: Optional[Any] = None  # Optional[ProcessingConfig]

    def __post_init__(self) -> None:
        if self.docling_config is None:
            from .document_processor import ProcessingConfig
            self.docling_config = ProcessingConfig()


# ---------------------------------------------------------------------------
# Unified processor
# ---------------------------------------------------------------------------

class DocumentProcessorV2:
    """Unified smart router that dispatches each file to its optimal reader."""

    # All supported extensions (custom + Docling)
    SUPPORTED_EXTENSIONS: set[str] = {
        # Custom readers
        ".docx", ".doc",
        ".xlsx", ".xls", ".xlsm",
        ".pptx", ".ppt",
        ".pdf",
        # Docling
        ".html", ".htm", ".xhtml",
        ".md", ".txt",
        ".csv",
        ".adoc", ".asciidoc", ".asc",
        ".vtt",
        ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp",
    }

    def __init__(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[ProcessingConfigV2] = None,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or ProcessingConfigV2()

        self._setup_directories()
        self._setup_logging()

        # Lazy Docling converters
        self._primary_converter = None
        self._fallback_converter = None

        self.stats: Dict[str, Any] = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "processing_time": 0,
            "file_types": {},
            "errors": [],
        }

        logger.info("DocumentProcessorV2 initialised")
        logger.info("  input_dir : %s", self.input_dir)
        logger.info("  output_dir: %s", self.output_dir)

    # ------------------------------------------------------------------
    # Setup helpers (mirrors original)
    # ------------------------------------------------------------------

    def _setup_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)

    def _setup_logging(self) -> None:
        log_file = (
            self.output_dir
            / "logs"
            / f"processing_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
            )
        )
        logger.addHandler(fh)
        logger.info("V2 logging initialised -> %s", log_file)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_file_type(self, file_path: Path) -> str:
        """Return a human-readable file-type category string."""
        suffix = file_path.suffix.lower()
        _map = {
            ".docx": "docx", ".doc": "doc",
            ".xlsx": "xlsx", ".xls": "xls", ".xlsm": "xlsm",
            ".pptx": "pptx", ".ppt": "ppt",
            ".pdf": "pdf",
            ".html": "web", ".htm": "web", ".xhtml": "web",
            ".md": "text", ".txt": "text",
            ".csv": "csv",
            ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc",
            ".vtt": "webvtt",
            ".png": "image", ".jpg": "image", ".jpeg": "image",
            ".tiff": "image", ".tif": "image", ".bmp": "image", ".webp": "image",
        }
        return _map.get(suffix, "unknown")

    def is_supported_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def scan_input_directory(self) -> List[Path]:
        supported: List[Path] = []
        if not self.input_dir.exists():
            logger.error("Input directory does not exist: %s", self.input_dir)
            return supported
        for fp in self.input_dir.rglob("*"):
            if fp.is_file() and self.is_supported_format(fp):
                supported.append(fp)
        self.stats["total_files"] = len(supported)
        for fp in supported:
            ft = self.get_file_type(fp)
            self.stats["file_types"][ft] = self.stats["file_types"].get(ft, 0) + 1
        logger.info("Found %d supported files", len(supported))
        return supported

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route(self, file_path: Path) -> str:
        """Return the processor key for *file_path*."""
        if not self.config.prefer_custom_readers:
            return "docling"

        ext = file_path.suffix.lower()

        if ext in (".docx", ".doc"):
            return "docx_reader_v2"

        if ext in (".xlsx", ".xlsm", ".xls"):
            if self.config.excel_reader_mode == "xml":
                return "xlsx_reader_v2"
            return "docling"

        if ext in (".pptx", ".ppt"):
            if PPTX_READER_AVAILABLE:
                return "pptx_reader"
            logger.warning(
                "pptx_reader unavailable (missing app.* imports); "
                "routing %s to Docling",
                file_path.name,
            )
            return "docling"

        if ext == ".pdf":
            return self._route_pdf(file_path)

        return "docling"

    def _route_pdf(self, file_path: Path) -> str:
        """Route PDFs conservatively so scanned PDFs keep the Docling markdown path."""
        meta_path = self.input_dir / "normalization_metadata" / f"{file_path.stem}_pdf_classification.json"
        if not meta_path.exists():
            return "docling"

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            logger.warning("Could not read PDF classification metadata for %s: %s", file_path.name, exc)
            return "docling"

        pdf_type = str(meta.get("pdf_type", "")).strip().lower()
        if pdf_type == "born_digital":
            return "pdf_reader"
        return "docling"

    # ------------------------------------------------------------------
    # Per-reader private methods
    # ------------------------------------------------------------------

    def _run_docx_reader(
        self, file_path: Path, out_dir: Path,
    ) -> List[Dict[str, Any]]:
        from .docx_reader_v2 import DocxParser

        parser = DocxParser()
        return parser.extract_docx_text(str(file_path), output_dir=str(out_dir))

    def _run_xlsx_reader(
        self, file_path: Path, out_dir: Path,
    ) -> List[Dict[str, Any]]:
        from .xlsx_reader_v2 import process_excel_file

        json_path = process_excel_file(file_path, output_dir=out_dir)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # process_excel_file returns the full workbook JSON which has a
        # "sheets" key; return it as-is for the excel_sheets field.
        if isinstance(data, dict):
            return data.get("sheets", [data])
        return data if isinstance(data, list) else [data]

    def _run_pptx_reader(self, file_path: Path) -> List[Dict[str, Any]]:
        from .pptx_reader import PptxParser

        parser = PptxParser(
            validate_headers_with_llm=self.config.pptx_llm_validate_headers,
            repository_id="",
        )
        return parser.extract_pptx_text(str(file_path))

    def _run_pdf_reader(
        self, file_path: Path, out_dir: Path,
    ) -> List[Dict[str, Any]]:
        from .pdf_reader import CustomPdfConfig, CustomPdfReader

        cfg = CustomPdfConfig(
            content_source=self.config.pdf_content_source,
            enable_ocr=getattr(self.config.docling_config, "enable_ocr", True),
            extract_images=getattr(self.config.docling_config, "export_images", False),
        )
        reader = CustomPdfReader(cfg)
        return reader.read(str(file_path), output_dir=str(out_dir))

    def _run_docling(self, file_path: Path) -> Any:
        """Run Docling converter (primary → fallback on failure)."""
        converter = self._get_primary_converter()

        # Handle .txt → temp .md
        actual_path = file_path
        temp_created = False
        if file_path.suffix.lower() == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            md_path = file_path.parent / f"{file_path.stem}_temp.md"
            md_path.write_text(f"# {file_path.stem}\n\n{content}", encoding="utf-8")
            actual_path = md_path
            temp_created = True

        try:
            result = converter.convert(str(actual_path))
        except Exception as primary_err:
            logger.warning(
                "Primary Docling pipeline failed for %s: %s — trying fallback",
                file_path.name, primary_err,
            )
            fallback = self._get_fallback_converter()
            if fallback is not None:
                try:
                    result = fallback.convert(str(actual_path))
                except Exception as fb_err:
                    raise RuntimeError(
                        f"Both Docling pipelines failed. "
                        f"Primary: {primary_err} | Fallback: {fb_err}"
                    ) from fb_err
            else:
                raise
        finally:
            if temp_created and actual_path.exists():
                actual_path.unlink(missing_ok=True)

        return result

    # ------------------------------------------------------------------
    # Docling lazy factories (verbatim from document_processor.py)
    # ------------------------------------------------------------------

    def _get_primary_converter(self):
        if self._primary_converter is not None:
            return self._primary_converter

        from docling.document_converter import DocumentConverter, FormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        cfg = self.config.docling_config

        try:
            from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
            BACKEND = DoclingParseV4DocumentBackend
        except ImportError:
            try:
                from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
                BACKEND = DoclingParseDocumentBackend
            except ImportError:
                BACKEND = PyPdfiumDocumentBackend

        # OCR options
        ocr_opts = None
        try:
            from docling.datamodel.pipeline_options import RapidOcrOptions
            ocr_opts = RapidOcrOptions(lang=getattr(cfg, "ocr_languages", ["eng"]))
        except Exception:
            pass

        # VLM options
        vlm_opts = None
        enable_vlm = getattr(cfg, "enable_vlm", False)
        if enable_vlm:
            try:
                from docling.datamodel.pipeline_options import PictureDescriptionVlmOptions
                vlm_opts = PictureDescriptionVlmOptions(
                    repo_id="HuggingFaceTB/SmolVLM-256M-Instruct",
                    batch_size=4,
                    scale=2,
                    picture_area_threshold=0.0,
                    prompt="Describe this image in a few concise sentences.",
                    generation_config={"max_new_tokens": 200, "do_sample": False},
                )
            except Exception:
                pass

        pdf_kwargs: Dict[str, Any] = {
            "do_ocr": getattr(cfg, "enable_ocr", True),
            "do_table_structure": bool(getattr(cfg, "export_tables", False)),
            "generate_picture_images": bool(getattr(cfg, "export_images", False)),
            "generate_page_images": bool(getattr(cfg, "export_images", False)),
            "generate_table_images": bool(getattr(cfg, "export_tables", False)),
            "do_picture_classification": bool(enable_vlm),
            "do_picture_description": bool(enable_vlm),
            "images_scale": 2.0,
        }
        if ocr_opts is not None:
            pdf_kwargs["ocr_options"] = ocr_opts
        if enable_vlm and vlm_opts is not None:
            pdf_kwargs["picture_description_options"] = vlm_opts

        pdf_options = PdfPipelineOptions(**pdf_kwargs)

        format_options = {
            InputFormat.PDF: FormatOption(
                pipeline_cls=StandardPdfPipeline,
                backend=BACKEND,
                pipeline_options=pdf_options,
            ),
            InputFormat.IMAGE: FormatOption(
                pipeline_cls=StandardPdfPipeline,
                backend=BACKEND,
                pipeline_options=pdf_options,
            ),
        }

        allowed_formats = [
            InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.XLSX,
            InputFormat.HTML, InputFormat.IMAGE, InputFormat.MD, InputFormat.CSV,
            InputFormat.ASCIIDOC, InputFormat.VTT,
        ]

        self._primary_converter = DocumentConverter(
            allowed_formats=allowed_formats,
            format_options=format_options,
        )
        logger.info("Primary Docling converter initialised")
        return self._primary_converter

    def _get_fallback_converter(self):
        if self._fallback_converter is not None:
            return self._fallback_converter

        try:
            from docling.document_converter import DocumentConverter, FormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

            ocr_opts = None
            try:
                from docling.datamodel.pipeline_options import RapidOcrOptions
                ocr_opts = RapidOcrOptions(
                    lang=getattr(self.config.docling_config, "ocr_languages", ["eng"]),
                )
            except Exception:
                pass

            pdf_kwargs: Dict[str, Any] = {
                "do_ocr": getattr(self.config.docling_config, "enable_ocr", True),
                "do_table_structure": True,
                "generate_picture_images": True,
                "generate_page_images": False,
                "generate_table_images": True,
                "do_picture_classification": False,
                "do_picture_description": False,
                "images_scale": 1.0,
            }
            if ocr_opts is not None:
                pdf_kwargs["ocr_options"] = ocr_opts

            pdf_options = PdfPipelineOptions(**pdf_kwargs)
            format_options = {
                InputFormat.PDF: FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pdf_options,
                ),
                InputFormat.IMAGE: FormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pdf_options,
                ),
            }
            allowed_formats = [
                InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.XLSX,
                InputFormat.HTML, InputFormat.IMAGE, InputFormat.MD, InputFormat.CSV,
                InputFormat.ASCIIDOC, InputFormat.VTT,
            ]
            self._fallback_converter = DocumentConverter(
                allowed_formats=allowed_formats,
                format_options=format_options,
            )
            logger.info("Fallback Docling converter initialised")
            return self._fallback_converter
        except Exception as exc:
            logger.warning("Could not create fallback converter: %s", exc)
            return None

    # ------------------------------------------------------------------
    # process_single_file — main entry point
    # ------------------------------------------------------------------

    def process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single file and return a unified result dict."""
        start_time = datetime.now()
        file_path = Path(file_path)

        processor_key = self._route(file_path)
        ext = file_path.suffix.lower()

        try:
            file_size = file_path.stat().st_size
        except OSError:
            file_size = 0

        logger.info("Processing %s via %s", file_path.name, processor_key)

        # Attempt custom reader
        original_error: Optional[str] = None
        used_fallback = False

        try:
            if processor_key == "docx_reader_v2":
                out_dir = self.output_dir / file_path.stem
                out_dir.mkdir(parents=True, exist_ok=True)
                content_tree = self._run_docx_reader(file_path, out_dir)
                return self._build_result(
                    file_path=file_path, file_type=ext.lstrip("."),
                    processor_used="docx_reader_v2",
                    start_time=start_time, file_size=file_size,
                    content_tree=content_tree,
                )

            if processor_key == "xlsx_reader_v2":
                out_dir = self.output_dir / file_path.stem
                out_dir.mkdir(parents=True, exist_ok=True)
                sheets = self._run_xlsx_reader(file_path, out_dir)
                return self._build_result(
                    file_path=file_path, file_type=ext.lstrip("."),
                    processor_used="xlsx_reader_v2",
                    start_time=start_time, file_size=file_size,
                    excel_sheets=sheets,
                )

            if processor_key == "pptx_reader":
                content_tree = self._run_pptx_reader(file_path)
                return self._build_result(
                    file_path=file_path, file_type=ext.lstrip("."),
                    processor_used="pptx_reader",
                    start_time=start_time, file_size=file_size,
                    content_tree=content_tree,
                )

            if processor_key == "pdf_reader":
                out_dir = self.output_dir / file_path.stem
                out_dir.mkdir(parents=True, exist_ok=True)
                try:
                    content_tree = self._run_pdf_reader(file_path, out_dir)
                    return self._build_result(
                        file_path=file_path, file_type="pdf",
                        processor_used="pdf_reader",
                        start_time=start_time, file_size=file_size,
                        content_tree=content_tree,
                    )
                except Exception as pdf_err:
                    logger.warning(
                        "CustomPdfReader failed for %s: %s — falling back to Docling",
                        file_path.name, pdf_err,
                    )
                    original_error = str(pdf_err)
                    used_fallback = True
                    # Fall through to Docling below

            # --- Docling path (default or fallback) ---
            docling_result = self._run_docling(file_path)
            doc = docling_result.document
            pages = getattr(doc, "page_count", None)

            return self._build_result(
                file_path=file_path,
                file_type=ext.lstrip("."),
                processor_used="docling",
                start_time=start_time,
                file_size=file_size,
                docling_result=docling_result,
                doc_object=doc,
                pages=pages,
                used_fallback=used_fallback,
                error=original_error,
            )

        except Exception as exc:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error("Failed to process %s: %s", file_path.name, exc)
            error_msg = str(exc)
            if original_error:
                error_msg = f"Custom: {original_error} | Docling: {exc}"
            err = self._build_error_result(
                file_path, ext.lstrip("."), elapsed, file_size, error_msg,
            )
            self.stats["errors"].append(err)
            return err

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_processed_document(
        self, processing_info: Dict[str, Any],
    ) -> Dict[str, str]:
        """Export a processed document result to disk."""
        if not processing_info.get("success"):
            return {}

        if processing_info["processor_used"] == "docling":
            return self._export_docling(processing_info)

        return self._export_custom(processing_info)

    def _export_docling(self, info: Dict[str, Any]) -> Dict[str, str]:
        """Identical export logic to MultimodalDocumentProcessor."""
        doc = info.get("doc_object")
        if doc is None:
            return {}

        file_stem = Path(info["file_path"]).stem
        safe_stem = self._get_safe_output_path(file_stem)

        exported: Dict[str, str] = {}
        doc_dir = self.output_dir / safe_stem
        if doc_dir.exists():
            shutil.rmtree(doc_dir, ignore_errors=True)
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Markdown
        try:
            md = doc.export_to_markdown()
            md_path = doc_dir / f"{safe_stem}.md"
            md_path.write_text(md, encoding="utf-8")
            exported["markdown"] = str(md_path)
        except Exception as exc:
            logger.warning("Failed to export markdown: %s", exc)

        # Metadata
        meta = {
            "file_path": info["file_path"],
            "file_type": info["file_type"],
            "processor_used": "docling",
            "processing_time": info["processing_time"],
            "pages": info.get("pages"),
            "used_fallback": info.get("used_fallback", False),
        }
        meta_path = doc_dir / f"{safe_stem}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        exported["metadata"] = str(meta_path)

        return exported

    def _export_custom(self, info: Dict[str, Any]) -> Dict[str, str]:
        """Export custom-reader results as _parsed.json + _metadata.json."""
        file_stem = Path(info["file_path"]).stem
        safe_stem = self._get_safe_output_path(file_stem)

        doc_dir = self.output_dir / safe_stem
        doc_dir.mkdir(parents=True, exist_ok=True)

        exported: Dict[str, str] = {}

        # Parsed content
        content = info.get("content_tree") or info.get("excel_sheets")
        if content is not None:
            parsed_path = doc_dir / f"{safe_stem}_parsed.json"
            with open(parsed_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2, default=str)
            exported["parsed_json"] = str(parsed_path)

        markdown_text = self._build_custom_markdown(
            content_tree=info.get("content_tree"),
            excel_sheets=info.get("excel_sheets"),
            title=file_stem,
        )
        if markdown_text:
            md_path = doc_dir / f"{safe_stem}.md"
            md_path.write_text(markdown_text, encoding="utf-8")
            exported["markdown"] = str(md_path)

        # Metadata
        meta = {
            "file_path": info["file_path"],
            "file_type": info["file_type"],
            "processor_used": info["processor_used"],
            "processing_time": info["processing_time"],
            "pages": info.get("pages"),
            "used_fallback": info.get("used_fallback", False),
        }
        meta_path = doc_dir / f"{safe_stem}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        exported["metadata_json"] = str(meta_path)

        return exported

    def _build_custom_markdown(
        self,
        *,
        content_tree: Optional[List[Dict[str, Any]]],
        excel_sheets: Optional[List[Dict[str, Any]]],
        title: str,
    ) -> str:
        """Best-effort markdown export for custom-reader outputs."""
        if content_tree:
            lines: List[str] = []
            self._append_content_tree_markdown(content_tree, lines)
            text = "\n\n".join(line for line in lines if line is not None).strip()
            if text:
                return text

        if excel_sheets:
            lines = [f"# {title}", "", "This workbook was processed with the V2 custom reader."]
            for idx, sheet in enumerate(excel_sheets, 1):
                if not isinstance(sheet, dict):
                    lines.append(f"## Sheet {idx}")
                    lines.append(str(sheet))
                    continue
                sheet_name = (
                    sheet.get("sheet_name")
                    or sheet.get("name")
                    or sheet.get("title")
                    or f"Sheet {idx}"
                )
                lines.append(f"## {sheet_name}")
                summary = sheet.get("summary")
                if summary:
                    lines.append(str(summary))
                    continue
                tables = sheet.get("tables")
                if isinstance(tables, list) and tables:
                    lines.append(f"Detected {len(tables)} table(s).")
                else:
                    lines.append("Structured workbook content was extracted for downstream chunking.")
            return "\n\n".join(lines).strip()

        return ""

    def _append_content_tree_markdown(
        self,
        nodes: List[Dict[str, Any]],
        lines: List[str],
    ) -> None:
        for node in nodes or []:
            if not isinstance(node, dict):
                lines.append(str(node))
                continue

            heading = (
                node.get("heading_text")
                or node.get("title")
                or node.get("heading")
                or ""
            )
            heading_level = node.get("heading_level") or node.get("level") or 1
            try:
                level = max(1, min(int(heading_level), 6))
            except Exception:
                level = 1

            if heading:
                lines.append(f"{'#' * level} {str(heading).strip()}")

            content = node.get("content")
            if content:
                lines.append(str(content).strip())

            children = node.get("children")
            if isinstance(children, list) and children:
                self._append_content_tree_markdown(children, lines)

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def process_batch(
        self, file_paths: Optional[List[Path]] = None,
    ) -> Dict[str, Any]:
        if file_paths is None:
            file_paths = self.scan_input_directory()
        if not file_paths:
            logger.warning("No files found to process")
            return {"success": False, "message": "No files found"}

        batch_start = datetime.now()
        results: Dict[str, Any] = {
            "total_files": len(file_paths),
            "processed_files": 0,
            "failed_files": 0,
            "processing_time": 0,
            "results": [],
            "errors": [],
            "exported_files": {},
        }

        logger.info("Starting V2 batch processing of %d files", len(file_paths))

        for idx, fp in enumerate(file_paths, 1):
            logger.info("Processing file %d/%d: %s", idx, len(file_paths), fp.name)
            info = self.process_single_file(fp)

            if info["success"]:
                exported = self.export_processed_document(info)
                info["exported_files"] = exported
                results["processed_files"] += 1
                results["results"].append(info)
                self.stats["processed_files"] += 1
            else:
                results["failed_files"] += 1
                results["errors"].append(info)
                self.stats["failed_files"] += 1

        results["processing_time"] = (datetime.now() - batch_start).total_seconds()
        self.stats["processing_time"] = results["processing_time"]
        logger.info(
            "Batch complete: %d/%d succeeded in %.1fs",
            results["processed_files"], results["total_files"],
            results["processing_time"],
        )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(
        *,
        file_path: Path,
        file_type: str,
        processor_used: str,
        start_time: datetime,
        file_size: int,
        content_tree: Optional[List[Dict]] = None,
        excel_sheets: Optional[List[Dict]] = None,
        docling_result: Optional[Any] = None,
        doc_object: Optional[Any] = None,
        pages: Optional[int] = None,
        used_fallback: bool = False,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "file_path": str(file_path),
            "file_type": file_type,
            "processor_used": processor_used,
            "processing_time": (datetime.now() - start_time).total_seconds(),
            "success": True,
            "error": error,
            "content_tree": content_tree,
            "excel_sheets": excel_sheets,
            "docling_result": docling_result,
            "doc_object": doc_object,
            "used_fallback": used_fallback,
            "pages": pages,
            "file_size": file_size,
        }

    @staticmethod
    def _build_error_result(
        file_path: Path,
        file_type: str,
        elapsed: float,
        file_size: int,
        error: str,
    ) -> Dict[str, Any]:
        return {
            "file_path": str(file_path),
            "file_type": file_type,
            "processor_used": "none",
            "processing_time": elapsed,
            "success": False,
            "error": error,
            "content_tree": None,
            "excel_sheets": None,
            "docling_result": None,
            "doc_object": None,
            "used_fallback": False,
            "pages": None,
            "file_size": file_size,
        }

    @staticmethod
    def _get_safe_output_path(filename: str, max_length: int = 50) -> str:
        filename = sanitize_filename_stem(filename)
        if len(filename) <= max_length:
            return filename
        hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
        truncated = filename[: max_length - 9]
        return f"{truncated}_{hash_suffix}"
