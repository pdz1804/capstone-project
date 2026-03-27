"""
DOCX Preprocessor for RAG Pipeline

Converts the JSON output of ``docx_reader_v2`` (hierarchical heading tree)
into the RAG-ready directory structure expected by the retrieval pipeline:

    stage4_rag_ready/
        <doc_id>/
            <doc_id>.md          ← combined Markdown (all sections)
            docx_chunks.json     ← pre-built chunks with heading metadata
            docx_manifest.json   ← identifies this as a DOCX document
            images/              ← extracted images (copied from parsed dir)

The manifest file mirrors ``excel_manifest.json`` / ``media_manifest.json``,
so the retrieval layer can distinguish DOCX docs and load their pre-built
chunks (which are heading- and table-aware) instead of blindly re-chunking
the Markdown file.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from .docx_chunker import DocxTableChunker, DocxChunkingConfig, IMAGE_PATH_PATTERN

logger = logging.getLogger(__name__)


class DocxPreprocessor:
    """
    Convert parsed DOCX JSON → RAG-ready folder structure.

    Usage::

        preprocessor = DocxPreprocessor(output_dir="stage4_rag_ready")
        preprocessor.process_docx_json(
            json_path="output/docx/spec_293.json",
            original_docx_path="raw/docx/spec_293.docx",
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

        self.chunker = DocxTableChunker(
            DocxChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                max_table_chunk_size=max_table_chunk_size,
            )
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_docx_json(
        self,
        json_path: Union[str, Path],
        original_docx_path: Optional[Union[str, Path]] = None,
        doc_id: Optional[str] = None,
    ) -> Dict:
        """
        Process a single parsed DOCX JSON file into RAG-ready format.

        Args:
            json_path: Path to the JSON produced by ``docx_reader_v2``.
            original_docx_path: Path to the original ``.docx`` file (for
                metadata; images are resolved relative to the parsed dir).
            doc_id: Override document ID. Defaults to the JSON file stem.

        Returns:
            Summary dict with ``doc_id``, ``num_sections``, ``num_chunks``,
            ``num_images``, ``output_folder``.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"DOCX JSON not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            tree: List[Dict] = json.load(f)

        if doc_id is None:
            doc_id = json_path.stem

        source = str(original_docx_path) if original_docx_path else str(json_path)
        uploaded_ts = datetime.now().isoformat()

        # 1. Create output folder
        doc_folder = self.output_dir / doc_id
        doc_folder.mkdir(parents=True, exist_ok=True)

        # 2. Build combined Markdown
        md_content = self._build_markdown(tree, doc_id)
        md_path = doc_folder / f"{doc_id}.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Wrote combined Markdown: {md_path}")

        # 3. Chunk with table-aware / heading-aware chunker
        chunks = self.chunker.chunk_docx_json(
            tree,
            doc_id=doc_id,
            source=source,
            uploaded_timestamp=uploaded_ts,
        )

        # 4. Save pre-built chunks
        num_sections = self._count_sections(tree)
        chunks_data = {
            "metadata": {
                "doc_id": doc_id,
                "source": source,
                "num_sections": num_sections,
                "total_chunks": len(chunks),
                "chunking_config": {
                    "chunk_size": self.chunker.docx_config.chunk_size,
                    "chunk_overlap": self.chunker.docx_config.chunk_overlap,
                    "max_table_chunk_size": self.chunker.docx_config.max_table_chunk_size,
                },
                "created_at": uploaded_ts,
            },
            "chunks": chunks,
        }
        chunks_path = doc_folder / "docx_chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Wrote {len(chunks)} chunks: {chunks_path}")

        # 5. Extract and copy images
        image_paths = self._collect_and_copy_images(tree, doc_folder)

        # 6. Write manifest
        manifest = {
            "document_type": "document",
            "doc_id": doc_id,
            "source": source,
            "num_sections": num_sections,
            "has_docx_chunks": True,
            "has_images": len(image_paths) > 0,
            "num_images": len(image_paths),
            "consolidated_at": uploaded_ts,
            "source_stage": "docx_preprocessor",
        }
        manifest_path = doc_folder / "docx_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        summary = {
            "doc_id": doc_id,
            "num_sections": num_sections,
            "num_chunks": len(chunks),
            "num_images": len(image_paths),
            "output_folder": str(doc_folder),
        }
        logger.info(f"DOCX preprocessor complete: {summary}")
        return summary

    # ------------------------------------------------------------------
    # Markdown builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_markdown(
        tree: List[Dict], doc_id: str, depth: int = 0
    ) -> str:
        """
        Recursively convert the heading tree into a single Markdown document.

        Heading levels are mapped to ``#`` depth. The original table and
        image markers are preserved for the chunker.
        """
        parts: List[str] = []
        if depth == 0:
            parts.append(f"# {doc_id}\n")

        for node in tree:
            heading = node.get("heading_text", "")
            level = node.get("heading_level", 1)
            content = node.get("content", "").strip()
            children = node.get("children", [])

            # Heading
            if heading:
                md_level = min(level + 1, 6)  # offset by 1 (doc title is #)
                parts.append(f"\n{'#' * md_level} {heading}\n")

            # Content
            if content:
                parts.append(content)
                parts.append("")  # blank line

            # Children
            if children:
                child_md = DocxPreprocessor._build_markdown(
                    children, doc_id, depth=depth + 1
                )
                parts.append(child_md)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Counting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_sections(tree: List[Dict]) -> int:
        """Count total number of nodes in the heading tree."""
        count = 0
        for node in tree:
            count += 1
            children = node.get("children", [])
            if children:
                count += DocxPreprocessor._count_sections(children)
        return count

    # ------------------------------------------------------------------
    # Image handling
    # ------------------------------------------------------------------

    def _collect_and_copy_images(
        self, tree: List[Dict], doc_folder: Path
    ) -> List[str]:
        """
        Find all ``[START_IMAGE_PATH]...[END_IMAGE_PATH]`` paths across
        the heading tree, copy the image files into ``doc_folder/images/``,
        and return the list of (original) image paths found.
        """
        all_image_paths = self._gather_image_paths(tree)

        if not all_image_paths:
            return []

        images_dir = doc_folder / "images"
        images_dir.mkdir(exist_ok=True)

        copied = []
        for img_entry in all_image_paths:
            # Image path may be "path|hash" — take only the path
            path_str = img_entry.split("|")[0].strip()
            img_path = Path(path_str)
            if img_path.exists():
                dest = images_dir / img_path.name
                try:
                    shutil.copy2(img_path, dest)
                    copied.append(str(img_path))
                    logger.debug(f"Copied image: {img_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to copy image {img_path}: {e}")
            else:
                logger.warning(f"Image not found: {path_str}")
                copied.append(path_str)

        logger.info(f"Collected {len(copied)} images into {images_dir}")
        return copied

    @staticmethod
    def _gather_image_paths(tree: List[Dict]) -> List[str]:
        """Recursively collect all image paths from the heading tree."""
        paths: List[str] = []
        for node in tree:
            content = node.get("content", "")
            paths.extend(IMAGE_PATH_PATTERN.findall(content))
            children = node.get("children", [])
            if children:
                paths.extend(DocxPreprocessor._gather_image_paths(children))
        return paths


# ---------------------------------------------------------------------------
# CLI / convenience
# ---------------------------------------------------------------------------

def preprocess_docx_for_rag(
    json_path: Union[str, Path],
    output_dir: Union[str, Path],
    original_docx_path: Optional[Union[str, Path]] = None,
    doc_id: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
) -> Dict:
    """
    One-call convenience to preprocess a DOCX JSON for the RAG pipeline.
    """
    preprocessor = DocxPreprocessor(
        output_dir=output_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    return preprocessor.process_docx_json(
        json_path=json_path,
        original_docx_path=original_docx_path,
        doc_id=doc_id,
    )
