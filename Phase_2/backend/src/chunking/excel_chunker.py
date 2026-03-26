"""
Table-Aware Chunking for Excel/Spreadsheet Documents

Extends the base TextChunker to handle structured content from parsed Excel files:
- Detects [START_TABLE]...[END_TABLE] markers and keeps tables intact or splits
  them row-by-row while repeating the Markdown header in every chunk.
- Detects [START_IMAGE]...[END_IMAGE] markers and extracts image paths for
  multimodal RAG integration.
- Preserves sheet-level metadata (sheet_name) through the chunking pipeline.
- **Table-aware parsing**: parses markdown tables into structured TableBlock/Row/Cell
  objects, then serializes each row as key-value text for better embeddings.
- **Entity docs**: per-row micro-documents for precise retrieval (course code, lecturer).
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

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

# Regex to extract markdown links: [text](url)
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


# ──────────────────────────────────────────────────────────────────
# Structured data types for table-aware parsing
# ──────────────────────────────────────────────────────────────────

@dataclass
class Link:
    text: str
    url: str


@dataclass
class Cell:
    raw: str          # original cell text (may contain markdown links)
    text: str         # text with markdown links stripped
    links: List[Link] = field(default_factory=list)


@dataclass
class Row:
    cells: Dict[str, Cell]  # key = column name
    row_index: int = 0


@dataclass
class TableBlock:
    sheet_name: str
    section_title: Optional[str]
    columns: List[str]
    rows: List[Row]
    table_id: str = ""

    def __post_init__(self):
        if not self.table_id:
            # Stable hash from sheet + section + columns + first 3 rows
            sig = f"{self.sheet_name}|{self.section_title}|{'|'.join(self.columns)}"
            for r in self.rows[:3]:
                sig += "|" + "|".join(c.text for c in r.cells.values())
            self.table_id = hashlib.md5(sig.encode("utf-8")).hexdigest()[:12]


# ──────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────

def _extract_links(raw: str) -> List[Link]:
    """Extract all markdown [text](url) links from raw cell text."""
    return [Link(text=m[0], url=m[1]) for m in _LINK_RE.findall(raw)]


def _strip_links(raw: str) -> str:
    """Replace [text](url) with just text."""
    return _LINK_RE.sub(r"\1", raw).strip()


def _parse_cell(raw: str) -> Cell:
    return Cell(raw=raw.strip(), text=_strip_links(raw), links=_extract_links(raw))


def _parse_md_row(line: str) -> List[str]:
    """Split a markdown table row ``| a | b | c |`` into cell strings."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_separator_line(line: str) -> bool:
    """Check if a line is a markdown table separator like | --- | --- |."""
    return bool(re.match(r"^\|[\s\-:|]+\|", line.strip()))


def parse_markdown_table(table_md: str) -> Tuple[List[str], List[Row]]:
    """
    Parse a markdown table string into (columns, rows).

    Returns:
        (columns: list[str], rows: list[Row])
    """
    lines = [l for l in table_md.split("\n") if l.strip()]
    if len(lines) < 2:
        return [], []

    # Header
    columns = [_strip_links(c) for c in _parse_md_row(lines[0])]

    # Find separator
    data_start = 1
    if len(lines) > 1 and _is_separator_line(lines[1]):
        data_start = 2

    rows: List[Row] = []
    for idx, line in enumerate(lines[data_start:]):
        raw_cells = _parse_md_row(line)
        cells: Dict[str, Cell] = {}
        for j, col in enumerate(columns):
            raw_val = raw_cells[j] if j < len(raw_cells) else ""
            cells[col] = _parse_cell(raw_val)
        rows.append(Row(cells=cells, row_index=idx))

    return columns, rows


def parse_sheet_to_table_blocks(sheet_name: str, content: str) -> List[TableBlock]:
    """
    Split sheet content into a list of ``TableBlock`` objects.

    Non-table text between markers is used as ``section_title`` context for
    the next table block (e.g. "TOÁN VÀ KHOA HỌC TỰ NHIÊN").
    """
    blocks: List[TableBlock] = []
    section_title: Optional[str] = None
    remaining = content

    while remaining:
        start_idx = remaining.find(TABLE_START_MARKER)
        if start_idx == -1:
            # No more tables — capture trailing text as section context (unused)
            break

        # Text before this table → section title
        before = remaining[:start_idx].strip()
        if before:
            # Last non-empty line before the table is the section title
            last_line = [l.strip() for l in before.splitlines() if l.strip()]
            if last_line:
                section_title = last_line[-1]

        # Find matching end marker
        end_idx = remaining.find(TABLE_END_MARKER, start_idx)
        if end_idx == -1:
            break  # malformed

        table_md = remaining[start_idx + len(TABLE_START_MARKER): end_idx].strip()
        remaining = remaining[end_idx + len(TABLE_END_MARKER):]

        columns, rows = parse_markdown_table(table_md)
        if columns and rows:
            blocks.append(TableBlock(
                sheet_name=sheet_name,
                section_title=section_title,
                columns=columns,
                rows=rows,
            ))

    return blocks


# ──────────────────────────────────────────────────────────────────
# Key-value serialization (much better for embeddings than raw markdown)
# ──────────────────────────────────────────────────────────────────

# Heuristic column name matchers (Vietnamese + English)
_CODE_HINTS = {"mã", "code"}
_NAME_HINTS = {"tên môn học", "tên môn", "name", "tên"}
_LECTURER_HINTS = {"giảng viên", "lecturer", "giáo viên"}
_VIDEO_HINTS = {"video"}
_MATERIAL_HINTS = {"tài liệu", "material"}
_NOTE_HINTS = {"ghi chú", "note", "notes"}


def _match_col(columns: List[str], hints: set) -> Optional[str]:
    """Find a column whose lower-cased name contains one of the hints."""
    for col in columns:
        low = col.lower().strip()
        if low in hints or any(h in low for h in hints):
            return col
    return None


def serialize_row_as_kv(table_block: TableBlock, row: Row) -> str:
    """
    Serialize a single row as key-value text for embedding.

    Example output::

        Sheet: ĐẠI CƯƠNG. Section: TOÁN VÀ KHOA HỌC TỰ NHIÊN.
        Course MT1003. Title: Giải tích 1. Lecturer: Võ Trần An.
        Video: Click here. Material: Tailieubachkhoa.
        Link(Video): Click here -> https://youtube.com/...
        Link(Tài liệu): Tailieubachkhoa -> https://drive.google.com/...
    """
    parts: List[str] = []
    if table_block.sheet_name:
        parts.append(f"Sheet: {table_block.sheet_name}.")
    if table_block.section_title:
        parts.append(f"Section: {table_block.section_title}.")

    # Emit each column as key-value
    for col in table_block.columns:
        cell = row.cells.get(col)
        if cell and cell.text:
            parts.append(f"{col}: {cell.text}.")

    # Emit all links explicitly
    for col in table_block.columns:
        cell = row.cells.get(col)
        if cell:
            for link in cell.links:
                parts.append(f"Link({col}): {link.text} -> {link.url}.")

    return " ".join(parts)


def serialize_table_chunk_kv(
    sheet: str,
    section: Optional[str],
    columns: List[str],
    rows: List[Row],
) -> str:
    """
    Serialize a group of rows as structured key-value text.

    Each row is prefixed with ``ROW:`` and each cell is listed as
    ``- ColName: value``, followed by links.
    """
    lines: List[str] = []
    lines.append(f"SHEET: {sheet}")
    if section:
        lines.append(f"SECTION: {section}")
    lines.append(f"COLUMNS: {' | '.join(columns)}")
    for r in rows:
        lines.append("ROW:")
        for col in columns:
            cell = r.cells.get(col)
            if cell and cell.text:
                lines.append(f"- {col}: {cell.text}")
                for link in cell.links:
                    lines.append(f"  LINK: {link.text} -> {link.url}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# Chunking config & class
# ──────────────────────────────────────────────────────────────────

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

    # Maximum rows per table chunk when splitting large tables
    max_rows_per_chunk: int = 15

    # Whether to generate per-row entity docs for precise retrieval
    enable_entity_docs: bool = True


class ExcelTableChunker(TextChunker):
    """
    Table-aware chunker for Excel-parsed content.

    Processing modes:
    1. **Table-aware (default)**: parses tables into structured TableBlock / Row
       objects, serializes as key-value text, and optionally generates per-row
       entity docs for precise retrieval.
    2. **Legacy**: splits content into text/table segments and delegates to the
       parent ``TextChunker.split_text`` (used only as fallback).
    """

    def __init__(self, config: Optional[ExcelChunkingConfig] = None):
        self.excel_config = config or ExcelChunkingConfig()
        # Initialise parent with the base ChunkingConfig fields
        super().__init__(self.excel_config)

    # ------------------------------------------------------------------
    # Segment splitting (legacy helper, still used by split_text)
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
    # Table splitting helpers (legacy)
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
    # split_text — kept for backward compat (used by non-Excel paths)
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

    # ------------------------------------------------------------------
    # Table-aware chunking (new): structured parsing + kv serialization
    # ------------------------------------------------------------------

    def _build_table_row_chunks(
        self,
        table_block: TableBlock,
        *,
        doc_id: str,
        source: str,
        uploaded_timestamp: str,
        original_file_format: str,
    ) -> List[Dict[str, Any]]:
        """
        Build chunks from a single TableBlock.

        Produces two kinds of chunks:
        - **Row-group chunks** (``type=table_rows``): groups of N rows serialized
          as key-value text, always include column header context.
        - **Entity docs** (``type=row_entity``): one per row, for precise retrieval
          by course code, lecturer, etc.
        """
        chunks: List[Dict[str, Any]] = []
        safe_sheet = re.sub(r"[^\w]+", "_", table_block.sheet_name).strip("_")
        base_id = f"{doc_id}__{safe_sheet}__{table_block.table_id}"

        cols = table_block.columns
        code_col = _match_col(cols, _CODE_HINTS)
        name_col = _match_col(cols, _NAME_HINTS)
        lecturer_col = _match_col(cols, _LECTURER_HINTS)

        rows = table_block.rows
        max_rpc = self.excel_config.max_rows_per_chunk

        # ── 1) Row-group chunks ──────────────────────────────────────
        for start in range(0, len(rows), max_rpc):
            end = min(start + max_rpc, len(rows))
            subset = rows[start:end]

            chunk_text = serialize_table_chunk_kv(
                sheet=table_block.sheet_name,
                section=table_block.section_title,
                columns=cols,
                rows=subset,
            )

            chunk_id = f"{base_id}_rows_{start}_{end - 1}"
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "source": source,
                "doc_id": f"{doc_id}__{safe_sheet}",
                "chunk_index": len(chunks),
                "is_table": True,
                "metadata": {
                    "doc_id": f"{doc_id}__{safe_sheet}",
                    "parent_doc_id": doc_id,
                    "chunk_type": "table_rows",
                    "sheet_name": table_block.sheet_name,
                    "section": table_block.section_title,
                    "table_id": table_block.table_id,
                    "columns": cols,
                    "row_start": start,
                    "row_end": end - 1,
                    "is_table": True,
                    "document_type": "spreadsheet",
                    "original_file": source,
                    "original_file_format": original_file_format,
                    "current_format": "key_value_table",
                    "uploaded_timestamp": uploaded_timestamp,
                    "content_type": "table_data",
                    "uniform_metadata_version": "1.0",
                },
            })

        # ── 2) Per-row entity docs ───────────────────────────────────
        if self.excel_config.enable_entity_docs:
            for row in rows:
                code = row.cells.get(code_col, Cell("", "")).text if code_col else None
                name = row.cells.get(name_col, Cell("", "")).text if name_col else None
                lecturer = row.cells.get(lecturer_col, Cell("", "")).text if lecturer_col else None

                row_text = serialize_row_as_kv(table_block, row)
                if not row_text.strip():
                    continue

                entity_key = code if code else f"row_{row.row_index}"
                entity_id = f"{base_id}_entity_{entity_key}_{row.row_index}"

                chunks.append({
                    "id": entity_id,
                    "text": row_text,
                    "source": source,
                    "doc_id": f"{doc_id}__{safe_sheet}",
                    "chunk_index": len(chunks),
                    "is_table": True,
                    "metadata": {
                        "doc_id": f"{doc_id}__{safe_sheet}",
                        "parent_doc_id": doc_id,
                        "chunk_type": "row_entity",
                        "sheet_name": table_block.sheet_name,
                        "section": table_block.section_title,
                        "table_id": table_block.table_id,
                        "row_index": row.row_index,
                        "entity_key": entity_key,
                        "course_code": code,
                        "course_name": name,
                        "lecturer": lecturer,
                        "is_table": True,
                        "document_type": "spreadsheet",
                        "original_file": source,
                        "original_file_format": original_file_format,
                        "current_format": "key_value_row",
                        "uploaded_timestamp": uploaded_timestamp,
                        "content_type": "row_entity",
                        "uniform_metadata_version": "1.0",
                    },
                })

        return chunks

    # ------------------------------------------------------------------
    # Public API — table-aware entry points
    # ------------------------------------------------------------------

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

        Uses table-aware parsing: markdown tables are parsed into structured
        TableBlock/Row objects and serialized as key-value text for better
        embedding quality.  Non-table text is chunked with the parent splitter.

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
        image_paths = (
            self._extract_image_paths(content)
            if self.excel_config.extract_images
            else []
        )

        original_file_format = ""
        if source:
            original_file_format = Path(source).suffix.lstrip(".").lower()
        if not uploaded_timestamp:
            uploaded_timestamp = datetime.now().isoformat()

        # Build a sheet-level ID
        safe_sheet = re.sub(r"[^\w]+", "_", sheet_name).strip("_")
        sheet_doc_id = f"{doc_id}__{safe_sheet}"

        # ── Parse tables into structured blocks ──────────────────────
        table_blocks = parse_sheet_to_table_blocks(sheet_name, content)

        chunks: List[Dict[str, Any]] = []

        if table_blocks:
            # Use structured table-aware chunking
            for tb in table_blocks:
                tb_chunks = self._build_table_row_chunks(
                    tb,
                    doc_id=doc_id,
                    source=source,
                    uploaded_timestamp=uploaded_timestamp,
                    original_file_format=original_file_format,
                )
                chunks.extend(tb_chunks)

            # Also chunk any non-table text between tables
            # (e.g. section titles, standalone paragraphs)
            segments = self._split_into_segments(content)
            for seg in segments:
                if seg["type"] == "text":
                    text_only = seg["content"].strip()
                    if len(text_only) >= self.excel_config.min_chunk_size:
                        text_chunks = super().split_text(text_only)
                        for tc in text_chunks:
                            chunk_id = f"{sheet_doc_id}_text_{len(chunks)}"
                            chunks.append({
                                "id": chunk_id,
                                "text": tc,
                                "source": source,
                                "doc_id": sheet_doc_id,
                                "chunk_index": len(chunks),
                                "is_table": False,
                                "metadata": {
                                    "doc_id": sheet_doc_id,
                                    "parent_doc_id": doc_id,
                                    "chunk_type": "text",
                                    "sheet_name": sheet_name,
                                    "is_table": False,
                                    "document_type": "spreadsheet",
                                    "original_file": source,
                                    "original_file_format": original_file_format,
                                    "current_format": "text",
                                    "uploaded_timestamp": uploaded_timestamp,
                                    "content_type": "document_text",
                                    "uniform_metadata_version": "1.0",
                                },
                            })
        else:
            # Fallback: no tables detected — use legacy split_text
            text_chunks = self.split_text(content)
            for i, chunk_text in enumerate(text_chunks):
                chunk_name = f"{sheet_doc_id}_chunk_{i}"
                is_table = (
                    chunk_text.strip().startswith("|")
                    or TABLE_START_MARKER in chunk_text
                )
                chunk_images = self._extract_image_paths(chunk_text)
                chunks.append({
                    "id": chunk_name,
                    "text": chunk_text,
                    "source": source,
                    "doc_id": sheet_doc_id,
                    "chunk_index": i,
                    "total_chunks": len(text_chunks),
                    "is_table": is_table,
                    "metadata": {
                        "doc_id": sheet_doc_id,
                        "parent_doc_id": doc_id,
                        "chunk_index": i,
                        "chunk_name": chunk_name,
                        "total_chunks": len(text_chunks),
                        "source": source,
                        "char_length": len(chunk_text),
                        "sheet_name": sheet_name,
                        "is_table": is_table,
                        "has_images": len(chunk_images) > 0,
                        "image_paths": chunk_images,
                        "document_type": "spreadsheet",
                        "original_file": source,
                        "original_file_format": original_file_format,
                        "current_format": "markdown_table" if is_table else "text",
                        "uploaded_timestamp": uploaded_timestamp,
                        "content_type": "table_data" if is_table else "document_text",
                        "uniform_metadata_version": "1.0",
                    },
                })

        # Re-index chunk_index + total_chunks
        for i, c in enumerate(chunks):
            c["chunk_index"] = i
            c["total_chunks"] = len(chunks)
            c["metadata"]["chunk_index"] = i
            c["metadata"]["total_chunks"] = len(chunks)

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


def save_chunks_to_file(
    sheets: List[Dict[str, Any]],
    *,
    doc_id: str = "excel_doc",
    source: str = "",
    out_dir: str | Path = "output_chunk",
) -> Path:
    """
    Convenience: chunk the parsed Excel JSON and save chunks to `out_dir/<doc_id>_chunks.json`.

    Returns the Path to the written file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = chunk_excel_json(sheets, doc_id=doc_id, source=source)
    out_path = out_dir / (f"{doc_id}_chunks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2, default=str)
    return out_path
