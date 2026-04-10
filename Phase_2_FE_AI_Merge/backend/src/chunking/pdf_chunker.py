"""
Table-Aware Chunking for Born-Digital PDF Documents

Extends ``DocxTableChunker`` since the parsed JSON format from
``pdf_reader.py`` is identical to ``docx_reader_v2.py``:

    {
        "heading_text": str,
        "heading_level": int,
        "children": [...],
        "content": str          # may contain table/image markers
    }

Overrides metadata fields to reflect PDF origin (document_type,
original_file_format, source_parser).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from .docx_chunker import DocxChunkingConfig, DocxTableChunker

logger = logging.getLogger(__name__)


@dataclass
class PdfChunkingConfig(DocxChunkingConfig):
    """Configuration for PDF-aware chunking.

    Inherits all DOCX chunking parameters since the content
    structure is identical.
    """
    pass


class PdfTableChunker(DocxTableChunker):
    """Table-aware chunker for born-digital PDF content.

    Delegates all chunking logic to ``DocxTableChunker`` and
    patches metadata to reflect PDF origin.
    """

    def chunk_pdf_json(
        self,
        tree: List[Dict[str, Any]],
        *,
        doc_id: str,
        source: str = "",
        uploaded_timestamp: str = "",
    ) -> List[Dict[str, Any]]:
        """Chunk a parsed PDF heading tree.

        Args:
            tree: Hierarchical JSON list from ``PdfParser.parse()``.
            doc_id: Document-level identifier (filename stem).
            source: Path to the original PDF file.
            uploaded_timestamp: ISO timestamp.

        Returns:
            List of chunk dicts with PDF-specific metadata.
        """
        chunks = self.chunk_docx_json(
            tree,
            doc_id=doc_id,
            source=source,
            uploaded_timestamp=uploaded_timestamp,
        )

        # Override metadata to reflect PDF source
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            meta["document_type"] = "pdf_document"
            meta["original_file_format"] = "pdf"
            meta["source_parser"] = "pdf_reader"

        logger.info(
            f"PDF '{doc_id}': produced {len(chunks)} chunks "
            f"(via DocxTableChunker with PDF metadata)"
        )
        return chunks


def chunk_pdf_json(
    tree: List[Dict[str, Any]],
    *,
    doc_id: str = "pdf_doc",
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
) -> List[Dict[str, Any]]:
    """One-call convenience to chunk parsed PDF JSON output.

    Args:
        tree: Parsed JSON (hierarchical list from ``pdf_reader``).
        doc_id: Document identifier.
        source: Original file path.
        chunk_size: Max chunk size in characters.
        chunk_overlap: Overlap between text chunks.
        max_table_chunk_size: Max table chunk before row-by-row split.

    Returns:
        List of chunk dicts.
    """
    config = PdfChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    chunker = PdfTableChunker(config)
    return chunker.chunk_pdf_json(tree, doc_id=doc_id, source=source)
