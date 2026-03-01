"""
Table-Aware Chunking for Excel/Spreadsheet Documents

Extends the base TextChunker to handle structured content from parsed Excel files:
- Detects [START_TABLE]...[END_TABLE] markers and keeps tables intact or splits
  them row-by-row while repeating the Markdown header in every chunk.
- Detects [START_IMAGE]...[END_IMAGE] markers and extracts image paths for
  multimodal RAG integration.
- Preserves sheet-level metadata (sheet_name) through the chunking pipeline.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .chunker import ChunkingConfig, TextChunker

logger = logging.getLogger(__name__)

# Markers consistent with xlsx_reader_v2.py / docx_reader.py
TABLE_START_MARKER = "[START_TABLE]"
TABLE_END_MARKER = "[END_TABLE]"
IMAGE_START_MARKER = "[START_IMAGE]"
IMAGE_END_MARKER = "[END_IMAGE]"

# Regex to find image markers
IMAGE_PATTERN = re.compile(
    r"\[START_IMAGE\](.*?)\[END_IMAGE\]", re.DOTALL
)


@dataclass
class ExcelChunkingConfig(ChunkingConfig):
    """Extended configuration for Excel-aware chunking."""

    # Maximum characters for a table before splitting it row-by-row
    max_table_chunk_size: int = 2000

    # If True, always keep a table in one chunk even if it exceeds chunk_size
    # (up to max_table_chunk_size). Beyond that, split by rows.
    prefer_whole_tables: bool = True

    # Whether to extract image paths from [START_IMAGE]...[END_IMAGE] markers
    extract_images: bool = True


class ExcelTableChunker(TextChunker):
    """
    Table-aware chunker for Excel-parsed content.

    Processing order:
    1. Split the content into *segments*: alternating text blocks and table blocks
       (delimited by [START_TABLE]...[END_TABLE]).
    2. For each **text segment**, delegate to the parent ``TextChunker.split_text``.
    3. For each **table segment**:
       a. If the table fits within ``max_table_chunk_size``, keep it as one chunk.
       b. Otherwise, split the table by rows, repeating the Markdown header row
          and separator row in every resulting chunk.
    4. Extract image paths from ``[START_IMAGE]...[END_IMAGE]`` markers and
       attach them as metadata.
    """

    def __init__(self, config: Optional[ExcelChunkingConfig] = None):
        self.excel_config = config or ExcelChunkingConfig()
        # Initialise parent with the base ChunkingConfig fields
        super().__init__(self.excel_config)

    # ------------------------------------------------------------------
    # Segment splitting
    # ------------------------------------------------------------------

    @staticmethod
    def _split_into_segments(text: str) -> List[Dict[str, Any]]:
        """
        Split *text* into ordered segments of type ``'text'`` or ``'table'``.

        Returns a list of dicts:
            {"type": "text"|"table", "content": str}
        """
        segments: List[Dict[str, Any]] = []
        remaining = text
        while remaining:
            start_idx = remaining.find(TABLE_START_MARKER)
            if start_idx == -1:
                # No more tables – rest is plain text
                if remaining.strip():
                    segments.append({"type": "text", "content": remaining})
                break

            # Text before the table
            before = remaining[:start_idx]
            if before.strip():
                segments.append({"type": "text", "content": before})

            # Find matching end marker
            end_idx = remaining.find(TABLE_END_MARKER, start_idx)
            if end_idx == -1:
                # Malformed – treat remainder as text
                segments.append({"type": "text", "content": remaining[start_idx:]})
                break

            table_content = remaining[
                start_idx + len(TABLE_START_MARKER): end_idx
            ].strip()
            segments.append({"type": "table", "content": table_content})
            remaining = remaining[end_idx + len(TABLE_END_MARKER):]

        return segments

    # ------------------------------------------------------------------
    # Table splitting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_md_table(table_md: str) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Parse a Markdown table into header, separator, and data rows.

        Returns:
            (header_line, separator_line, data_lines)
        """
        lines = [l for l in table_md.split("\n") if l.strip()]
        if len(lines) < 2:
            return None, None, lines

        header = lines[0]
        separator = lines[1] if re.match(r"^\|[\s\-:|]+\|", lines[1]) else None
        data_start = 2 if separator else 1
        data_lines = lines[data_start:]
        return header, separator, data_lines

    def _split_table(self, table_md: str) -> List[str]:
        """
        Split a large Markdown table into multiple chunks, each starting with
        the original header + separator row.
        """
        header, separator, data_lines = self._parse_md_table(table_md)
        if not data_lines:
            return [table_md] if table_md.strip() else []

        # Build the prefix that every chunk must start with
        prefix_parts = []
        if header:
            prefix_parts.append(header)
        if separator:
            prefix_parts.append(separator)
        prefix = "\n".join(prefix_parts)
        prefix_len = len(prefix) + 1  # +1 for the newline after prefix

        # Greedily pack rows into chunks
        chunks: List[str] = []
        current_rows: List[str] = []
        current_len = prefix_len

        for row in data_lines:
            row_len = len(row) + 1  # +1 for newline
            if current_rows and (current_len + row_len) > self.excel_config.max_table_chunk_size:
                # Flush current chunk
                chunk_text = prefix + "\n" + "\n".join(current_rows)
                chunks.append(chunk_text)
                current_rows = []
                current_len = prefix_len

            current_rows.append(row)
            current_len += row_len

        # Flush remaining
        if current_rows:
            chunk_text = prefix + "\n" + "\n".join(current_rows)
            chunks.append(chunk_text)

        return chunks

    # ------------------------------------------------------------------
    # Image extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_image_paths(text: str) -> List[str]:
        """Return all image file paths found in [START_IMAGE]...[END_IMAGE] markers."""
        return IMAGE_PATTERN.findall(text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split_text(self, text: str) -> List[str]:
        """
        Split text that may contain [START_TABLE] / [END_TABLE] markers.

        Tables are kept whole when they fit within ``max_table_chunk_size``;
        otherwise they are split row-by-row with the header repeated.
        Non-table text is chunked using the parent recursive splitter.
        """
        if not text:
            return []

        segments = self._split_into_segments(text)
        all_chunks: List[str] = []

        for seg in segments:
            if seg["type"] == "table":
                table_md = seg["content"]
                if (
                    self.excel_config.prefer_whole_tables
                    and len(table_md) <= self.excel_config.max_table_chunk_size
                ):
                    all_chunks.append(table_md)
                else:
                    all_chunks.extend(self._split_table(table_md))
            else:
                # Delegate plain text to parent chunker
                text_chunks = super().split_text(seg["content"])
                all_chunks.extend(text_chunks)

        # Post-filter: skip tiny chunks
        return [
            c for c in all_chunks
            if len(c.strip()) >= self.excel_config.min_chunk_size
        ]

    def chunk_excel_document(
        self,
        sheet: Dict[str, Any],
        *,
        doc_id: str,
        source: str = "",
        uploaded_timestamp: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single Excel *sheet* dict (as produced by ``xlsx_reader_v2``).

        Args:
            sheet: Dict with ``sheet_name`` and ``content`` keys.
            doc_id: Base document ID (e.g. filename stem).
            source: Path to the original Excel file.
            uploaded_timestamp: ISO timestamp of upload.

        Returns:
            List of chunk dicts ready for indexing.
        """
        sheet_name = sheet.get("sheet_name", "Sheet")
        content = sheet.get("content", "")
        if not content.strip():
            return []

        # Extract images before chunking
        image_paths = self._extract_image_paths(content) if self.excel_config.extract_images else []

        # Build a sheet-level ID
        safe_sheet = re.sub(r"[^\w]+", "_", sheet_name).strip("_")
        sheet_doc_id = f"{doc_id}__{safe_sheet}"

        text_chunks = self.split_text(content)

        original_file_format = ""
        if source:
            original_file_format = Path(source).suffix.lstrip(".").lower()
        if not uploaded_timestamp:
            uploaded_timestamp = datetime.now().isoformat()

        chunks: List[Dict[str, Any]] = []
        for i, chunk_text in enumerate(text_chunks):
            chunk_name = f"{sheet_doc_id}_chunk_{i}"

            # Determine content type
            is_table = (
                chunk_text.strip().startswith("|")
                or TABLE_START_MARKER in chunk_text
            )
            # Collect images referenced inside this chunk
            chunk_images = self._extract_image_paths(chunk_text)

            chunk = {
                "id": chunk_name,
                "text": chunk_text,
                "source": source,
                "doc_id": sheet_doc_id,
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "metadata": {
                    "doc_id": sheet_doc_id,
                    "parent_doc_id": doc_id,
                    "chunk_index": i,
                    "chunk_name": chunk_name,
                    "total_chunks": len(text_chunks),
                    "source": source,
                    "char_length": len(chunk_text),
                    # --- Excel-specific metadata ---
                    "sheet_name": sheet_name,
                    "is_table": is_table,
                    "has_images": len(chunk_images) > 0,
                    "image_paths": chunk_images,
                    # --- Uniform metadata fields ---
                    "document_type": "spreadsheet",
                    "original_file": source,
                    "original_file_format": original_file_format,
                    "current_format": "markdown_table" if is_table else "text",
                    "uploaded_timestamp": uploaded_timestamp,
                    "content_type": "table_data" if is_table else "document_text",
                    "uniform_metadata_version": "1.0",
                },
            }
            chunks.append(chunk)

        logger.info(
            f"Sheet '{sheet_name}' → {len(chunks)} chunks "
            f"({len(image_paths)} images detected)"
        )
        return chunks

    def chunk_excel_json(
        self,
        sheets: List[Dict[str, Any]],
        *,
        doc_id: str,
        source: str = "",
        uploaded_timestamp: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Chunk an entire parsed Excel workbook (list of sheet dicts).

        Args:
            sheets: List of dicts with ``sheet_name`` and ``content`` keys
                    (the JSON output of ``xlsx_reader_v2``).
            doc_id: Workbook-level identifier.
            source: Path to the original ``.xlsx`` file.
            uploaded_timestamp: ISO timestamp.

        Returns:
            List of all chunks across all sheets, ready for indexing.
        """
        all_chunks: List[Dict[str, Any]] = []
        for sheet in sheets:
            sheet_chunks = self.chunk_excel_document(
                sheet,
                doc_id=doc_id,
                source=source,
                uploaded_timestamp=uploaded_timestamp,
            )
            all_chunks.extend(sheet_chunks)

        logger.info(
            f"Workbook '{doc_id}': {len(sheets)} sheets → "
            f"{len(all_chunks)} total chunks"
        )
        return all_chunks


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def chunk_excel_json(
    sheets: List[Dict[str, Any]],
    *,
    doc_id: str = "excel_doc",
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
) -> List[Dict[str, Any]]:
    """
    One-call convenience to chunk parsed Excel JSON output.

    Args:
        sheets: Parsed JSON (list of ``{sheet_name, content}``).
        doc_id: Document identifier.
        source: Original file path.
        chunk_size: Max chars for non-table text chunks.
        chunk_overlap: Overlap for non-table text chunks.
        max_table_chunk_size: Max chars for a single table chunk before splitting.

    Returns:
        Flat list of chunk dicts.
    """
    config = ExcelChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    chunker = ExcelTableChunker(config)
    return chunker.chunk_excel_json(sheets, doc_id=doc_id, source=source)
