"""
Excel Preprocessor for RAG Pipeline

Converts the JSON output of ``xlsx_reader_v2`` into the RAG-ready directory
structure expected by the retrieval pipeline:

    stage4_rag_ready/
        <doc_id>/
            <doc_id>.md          ← combined Markdown (all sheets)
            excel_chunks.json    ← pre-built chunks with uniform metadata
            excel_manifest.json  ← identifies this as an Excel document
            images/              ← extracted images (copied from parsed dir)

The manifest file mirrors ``media_manifest.json`` used for video/audio, so
the retrieval layer can distinguish Excel docs and load their pre-built chunks
(which are table-aware) instead of blindly re-chunking the Markdown file.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from .excel_chunker import ExcelTableChunker, ExcelChunkingConfig, IMAGE_PATTERN

logger = logging.getLogger(__name__)


class ExcelPreprocessor:
    """
    Convert parsed Excel JSON → RAG-ready folder structure.

    Usage::

        preprocessor = ExcelPreprocessor(output_dir="stage4_rag_ready")
        preprocessor.process_excel_json(
            json_path="output/excel/courseware.json",
            original_xlsx_path="raw/excel/courseware.xlsx",   # optional
        )
    """

    def __init__(
        self,
        output_dir: Union[str, Path],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_table_chunk_size: int = 2000,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.chunker = ExcelTableChunker(
            ExcelChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                max_table_chunk_size=max_table_chunk_size,
            )
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_excel_json(
        self,
        json_path: Union[str, Path],
        original_xlsx_path: Optional[Union[str, Path]] = None,
        doc_id: Optional[str] = None,
    ) -> Dict:
        """
        Process a single parsed Excel JSON file into RAG-ready format.

        Args:
            json_path: Path to the JSON produced by ``xlsx_reader_v2``.
            original_xlsx_path: Path to the original ``.xlsx`` file (for
                metadata; images are resolved relative to the parsed dir).
            doc_id: Override document ID. Defaults to the JSON file stem.

        Returns:
            Summary dict with ``doc_id``, ``num_sheets``, ``num_chunks``,
            ``num_images``, ``output_folder``.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Excel JSON not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            sheets: List[Dict] = json.load(f)

        if doc_id is None:
            doc_id = json_path.stem

        source = str(original_xlsx_path) if original_xlsx_path else str(json_path)
        uploaded_ts = datetime.now().isoformat()

        # 1. Create output folder
        doc_folder = self.output_dir / doc_id
        doc_folder.mkdir(parents=True, exist_ok=True)

        # 2. Build combined Markdown
        md_content = self._build_markdown(sheets, doc_id)
        md_path = doc_folder / f"{doc_id}.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Wrote combined Markdown: {md_path}")

        # 3. Chunk with table-aware chunker
        chunks = self.chunker.chunk_excel_json(
            sheets,
            doc_id=doc_id,
            source=source,
            uploaded_timestamp=uploaded_ts,
        )

        # 4. Save pre-built chunks (mirrors transcript_chunks.json)
        chunks_data = {
            "metadata": {
                "doc_id": doc_id,
                "source": source,
                "num_sheets": len(sheets),
                "sheet_names": [s.get("sheet_name", "") for s in sheets],
                "total_chunks": len(chunks),
                "chunking_config": {
                    "chunk_size": self.chunker.excel_config.chunk_size,
                    "chunk_overlap": self.chunker.excel_config.chunk_overlap,
                    "max_table_chunk_size": self.chunker.excel_config.max_table_chunk_size,
                },
                "created_at": uploaded_ts,
            },
            "chunks": chunks,
        }
        chunks_path = doc_folder / "excel_chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Wrote {len(chunks)} chunks: {chunks_path}")

        # 5. Extract and copy images
        image_paths = self._collect_and_copy_images(sheets, doc_folder)

        # 6. Write manifest
        manifest = {
            "document_type": "spreadsheet",
            "doc_id": doc_id,
            "source": source,
            "num_sheets": len(sheets),
            "sheet_names": [s.get("sheet_name", "") for s in sheets],
            "has_excel_chunks": True,
            "has_images": len(image_paths) > 0,
            "num_images": len(image_paths),
            "consolidated_at": uploaded_ts,
            "source_stage": "excel_preprocessor",
        }
        manifest_path = doc_folder / "excel_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        summary = {
            "doc_id": doc_id,
            "num_sheets": len(sheets),
            "num_chunks": len(chunks),
            "num_images": len(image_paths),
            "output_folder": str(doc_folder),
        }
        logger.info(f"Excel preprocessor complete: {summary}")
        return summary

    # ------------------------------------------------------------------
    # Markdown builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_markdown(sheets: List[Dict], doc_id: str) -> str:
        """
        Combine all sheets into a single Markdown document.

        Each sheet gets a ``# Sheet: <name>`` heading.  The original
        ``[START_TABLE]`` / ``[END_TABLE]`` markers are preserved so
        the table-aware chunker can detect them later.
        """
        parts: List[str] = [f"# {doc_id}\n"]
        for sheet in sheets:
            name = sheet.get("sheet_name", "Unnamed Sheet")
            content = sheet.get("content", "").strip()
            parts.append(f"\n## Sheet: {name}\n")
            if content:
                parts.append(content)
            parts.append("")  # blank line after sheet

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Image handling
    # ------------------------------------------------------------------

    def _collect_and_copy_images(
        self, sheets: List[Dict], doc_folder: Path
    ) -> List[str]:
        """
        Find all ``[START_IMAGE]...[END_IMAGE]`` paths across sheets,
        copy the image files into ``doc_folder/images/``, and return the
        list of (original) image paths found.
        """
        all_image_paths: List[str] = []
        for sheet in sheets:
            content = sheet.get("content", "")
            all_image_paths.extend(IMAGE_PATTERN.findall(content))

        if not all_image_paths:
            return []

        images_dir = doc_folder / "images"
        images_dir.mkdir(exist_ok=True)

        copied = []
        for img_path_str in all_image_paths:
            img_path = Path(img_path_str.strip())
            if img_path.exists():
                dest = images_dir / img_path.name
                try:
                    shutil.copy2(img_path, dest)
                    copied.append(str(img_path))
                    logger.debug(f"Copied image: {img_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to copy image {img_path}: {e}")
            else:
                logger.warning(f"Image not found: {img_path_str}")
                # Still record it so metadata is aware
                copied.append(img_path_str)

        logger.info(f"Collected {len(copied)} images into {images_dir}")
        return copied


# ---------------------------------------------------------------------------
# CLI / convenience
# ---------------------------------------------------------------------------

def preprocess_excel_for_rag(
    json_path: Union[str, Path],
    output_dir: Union[str, Path],
    original_xlsx_path: Optional[Union[str, Path]] = None,
    doc_id: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
) -> Dict:
    """
    One-call convenience to preprocess an Excel JSON for the RAG pipeline.
    """
    preprocessor = ExcelPreprocessor(
        output_dir=output_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    return preprocessor.process_excel_json(
        json_path=json_path,
        original_xlsx_path=original_xlsx_path,
        doc_id=doc_id,
    )
