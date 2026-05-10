"""
Table-Aware Chunking for DOCX Documents

Extends the base TextChunker to handle structured content parsed by
``docx_reader_v2.py``.  The reader produces a hierarchical JSON tree where
each node has:

    {
        "heading_text": str,
        "heading_level": int,
        "children": [...],
        "content": str
    }

Content strings may contain the following inline markers:
    [START_TABLE_CONTENT] ... [END_TABLE_CONTENT]
    [START_IMAGE_PATH] path|hash [END_IMAGE_PATH]
    [START_SHAPE_CONTENT] ... [END_SHAPE_CONTENT]

This chunker:
- Walks the heading tree depth-first, producing one chunk per leaf section.
- Keeps tables intact when they fit, or splits them row-by-row with headers
  repeated (same logic as ``ExcelTableChunker``).
- Attaches heading breadcrumb metadata so the LLM knows where each chunk
  lives in the document hierarchy.
- Extracts image paths for multimodal integration.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .chunker import ChunkingConfig, TextChunker

# ── Formula-aware splitting helpers ──────────────────────────────────────────

_FORMULA_RE = re.compile(r"\$\$\n.*?\n\$\$", re.DOTALL)
_PLACEHOLDER_PREFIX = "\x00FORMULA_"
_PLACEHOLDER_SUFFIX = "\x00"


def _protect_formulas(text: str) -> Tuple[str, List[str]]:
    """Replace every formula (block or inline) with a unique placeholder.

    Returns the substituted text and an ordered list of original formula
    strings so they can be restored later.
    """
    formulas: List[str] = []

    def _replacer(m: re.Match) -> str:
        idx = len(formulas)
        formulas.append(m.group(0))
        return f"{_PLACEHOLDER_PREFIX}{idx}{_PLACEHOLDER_SUFFIX}"

    protected = _FORMULA_RE.sub(_replacer, text)  # only block $$...$$
    return protected, formulas


def _restore_formulas(text: str, formulas: List[str]) -> str:
    """Substitute placeholders back to their original formula strings."""
    def _replacer(m: re.Match) -> str:
        idx = int(m.group(1))
        return formulas[idx] if idx < len(formulas) else m.group(0)

    pattern = re.compile(
        re.escape(_PLACEHOLDER_PREFIX) + r"(\d+)" + re.escape(_PLACEHOLDER_SUFFIX)
    )
    return pattern.sub(_replacer, text)


def _split_text_formula_aware(
    splitter_fn,
    text: str,
) -> List[str]:
    """Split *text* while keeping ``$\\n...\\n$`` formula blocks atomic.

    Args:
        splitter_fn: Callable that accepts a string and returns List[str].
                     Typically ``TextChunker.split_text``.
        text: The raw text that may contain block formulas.

    Returns:
        List of text chunks with formulas fully restored.
    """
    protected, formulas = _protect_formulas(text)
    if not formulas:
        # Fast-path: no formulas, skip all overhead
        return splitter_fn(text)

    raw_chunks = splitter_fn(protected)
    return [_restore_formulas(c, formulas) for c in raw_chunks]

logger = logging.getLogger(__name__)

# ── Markers produced by docx_reader_v2 ───────────────────────────────────

TABLE_CONTENT_START = "[START_TABLE_CONTENT]"
TABLE_CONTENT_END = "[END_TABLE_CONTENT]"
IMAGE_PATH_START = "[START_IMAGE_PATH]"
IMAGE_PATH_END = "[END_IMAGE_PATH]"
SHAPE_CONTENT_START = "[START_SHAPE_CONTENT]"
SHAPE_CONTENT_END = "[END_SHAPE_CONTENT]"

# Regex helpers
IMAGE_PATH_PATTERN = re.compile(
    r"\[START_IMAGE_PATH\]\s*(.*?)\s*\[END_IMAGE_PATH\]", re.DOTALL
)
SHAPE_CONTENT_PATTERN = re.compile(
    r"\[START_SHAPE_CONTENT\]\s*(.*?)\s*\[END_SHAPE_CONTENT\]", re.DOTALL
)


# ───────────────────────────────────────────────────────────────────────────
# Segment utilities (table / text splitting)
# ───────────────────────────────────────────────────────────────────────────

def _split_into_segments(text: str) -> List[Dict[str, Any]]:
    """Split *text* into ordered segments of type ``'text'`` or ``'table'``.

    Returns a list of dicts: {"type": "text"|"table", "content": str}
    """
    segments: List[Dict[str, Any]] = []
    remaining = text
    while remaining:
        start_idx = remaining.find(TABLE_CONTENT_START)
        if start_idx == -1:
            if remaining.strip():
                segments.append({"type": "text", "content": remaining})
            break

        before = remaining[:start_idx]
        if before.strip():
            segments.append({"type": "text", "content": before})

        end_idx = remaining.find(TABLE_CONTENT_END, start_idx)
        if end_idx == -1:
            # Malformed   treat rest as text
            segments.append({"type": "text", "content": remaining[start_idx:]})
            break

        table_content = remaining[
            start_idx + len(TABLE_CONTENT_START): end_idx
        ].strip()
        segments.append({"type": "table", "content": table_content})
        remaining = remaining[end_idx + len(TABLE_CONTENT_END):]

    return segments


def _is_separator_line(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-:|]+\|", line.strip()))


def _parse_md_table(table_md: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Parse markdown table → (header, separator, data_rows)."""
    lines = [l for l in table_md.split("\n") if l.strip()]
    if len(lines) < 2:
        return None, None, lines
    header = lines[0]
    separator = lines[1] if _is_separator_line(lines[1]) else None
    data_start = 2 if separator else 1
    return header, separator, lines[data_start:]


def _split_large_table(table_md: str, max_size: int = 2000) -> List[str]:
    """Split a large markdown table into chunks, repeating the header."""
    header, separator, data_lines = _parse_md_table(table_md)
    if not data_lines:
        return [table_md] if table_md.strip() else []

    prefix_parts = []
    if header:
        prefix_parts.append(header)
    if separator:
        prefix_parts.append(separator)
    prefix = "\n".join(prefix_parts)
    prefix_len = len(prefix) + 1

    chunks: List[str] = []
    current_rows: List[str] = []
    current_len = prefix_len

    for row in data_lines:
        row_len = len(row) + 1
        if current_rows and (current_len + row_len) > max_size:
            chunks.append(prefix + "\n" + "\n".join(current_rows))
            current_rows = []
            current_len = prefix_len
        current_rows.append(row)
        current_len += row_len

    if current_rows:
        chunks.append(prefix + "\n" + "\n".join(current_rows))

    return chunks


# ───────────────────────────────────────────────────────────────────────────
# Heading-tree flattening
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class _FlatSection:
    """A flattened section produced by walking the heading tree."""
    heading_breadcrumb: List[str]      # e.g. ["3. Service", "3-1. Temporary map"]
    heading_level: int
    content: str                       # raw content string (may have markers)
    heading_text: str                  # the heading itself


def _flatten_tree(
    nodes: List[Dict[str, Any]],
    breadcrumb: Optional[List[str]] = None,
) -> List[_FlatSection]:
    """Recursively flatten the heading tree into a list of leaf sections."""
    if breadcrumb is None:
        breadcrumb = []

    sections: List[_FlatSection] = []
    for node in nodes:
        heading = node.get("heading_text", "")
        level = node.get("heading_level", 0)
        content = node.get("content", "")
        children = node.get("children", [])

        current_breadcrumb = breadcrumb + [heading] if heading else list(breadcrumb)

        # If there is content for this node, emit a section
        if content and content.strip():
            sections.append(_FlatSection(
                heading_breadcrumb=list(current_breadcrumb),
                heading_level=level,
                content=content,
                heading_text=heading,
            ))

        # Recurse into children
        if children:
            child_sections = _flatten_tree(children, current_breadcrumb)
            sections.extend(child_sections)

    return sections


# ───────────────────────────────────────────────────────────────────────────
# Chunking config & class
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class DocxChunkingConfig(ChunkingConfig):
    """Extended configuration for DOCX-aware chunking."""

    # Maximum characters for a table before splitting row-by-row
    max_table_chunk_size: int = 2000

    # Keep tables whole when they fit within max_table_chunk_size
    prefer_whole_tables: bool = True

    # Whether to extract image paths from markers
    extract_images: bool = True


class DocxTableChunker(TextChunker):
    """
    Table-aware chunker for DOCX-parsed content.

    Walks the hierarchical heading tree, splits content by table/text
    segments, and produces chunks with rich heading-context metadata.
    """

    def __init__(self, config: Optional[DocxChunkingConfig] = None):
        self.docx_config = config or DocxChunkingConfig()
        super().__init__(self.docx_config)

    # ------------------------------------------------------------------
    # Image / shape extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_image_paths(text: str) -> List[str]:
        """Return image file paths found in [START_IMAGE_PATH]...[END_IMAGE_PATH]."""
        raw = IMAGE_PATH_PATTERN.findall(text)
        paths: List[str] = []
        for entry in raw:
            # Format is: path|hash     we want just the path
            parts = entry.strip().split("|")
            if parts:
                paths.append(parts[0].strip())
        return paths

    # ------------------------------------------------------------------
    # Core split for a single section's content
    # ------------------------------------------------------------------

    def _chunk_section_content(
        self,
        section: _FlatSection,
        *,
        doc_id: str,
        source: str,
        uploaded_timestamp: str,
        original_file_format: str,
        global_chunk_index: int,
    ) -> List[Dict[str, Any]]:
        """Chunk the content of a single flat section.

        Returns a list of chunk dicts with proper metadata.
        """
        content = section.content
        if not content or not content.strip():
            return []

        segments = _split_into_segments(content)
        chunks: List[Dict[str, Any]] = []
        breadcrumb_str = " > ".join(section.heading_breadcrumb)

        for seg in segments:
            if seg["type"] == "table":
                table_md = seg["content"]
                if (
                    self.docx_config.prefer_whole_tables
                    and len(table_md) <= self.docx_config.max_table_chunk_size
                ):
                    table_texts = [table_md]
                else:
                    table_texts = _split_large_table(
                        table_md, self.docx_config.max_table_chunk_size
                    )

                for t_text in table_texts:
                    # Prepend heading context so the LLM knows where the
                    # table sits in the document
                    ctx = f"[Section: {breadcrumb_str}]\n\n" if breadcrumb_str else ""
                    chunk_text = ctx + t_text

                    idx = global_chunk_index + len(chunks)
                    chunk_id = f"{doc_id}_chunk_{idx}"
                    chunks.append({
                        "id": chunk_id,
                        "text": chunk_text,
                        "source": source,
                        "doc_id": doc_id,
                        "chunk_index": idx,
                        "is_table": True,
                        "metadata": {
                            "doc_id": doc_id,
                            "chunk_type": "table",
                            "heading_breadcrumb": section.heading_breadcrumb,
                            "heading_text": section.heading_text,
                            "heading_level": section.heading_level,
                            "is_table": True,
                            "document_type": "document",
                            "original_file": source,
                            "original_file_format": original_file_format,
                            "current_format": "markdown_table",
                            "uploaded_timestamp": uploaded_timestamp,
                            "content_type": "table_data",
                            "uniform_metadata_version": "1.0",
                        },
                    })
            else:
                # Plain text segment   use formula-aware splitter so that
                # $\n...\n$ blocks are never cut across chunk boundaries.
                text_parts = _split_text_formula_aware(
                    super().split_text, seg["content"]
                )
                for part in text_parts:
                    # Prepend heading context
                    ctx = f"[Section: {breadcrumb_str}]\n\n" if breadcrumb_str else ""
                    chunk_text = ctx + part

                    image_paths = self._extract_image_paths(part)
                    idx = global_chunk_index + len(chunks)
                    chunk_id = f"{doc_id}_chunk_{idx}"
                    chunks.append({
                        "id": chunk_id,
                        "text": chunk_text,
                        "source": source,
                        "doc_id": doc_id,
                        "chunk_index": idx,
                        "is_table": False,
                        "metadata": {
                            "doc_id": doc_id,
                            "chunk_type": "text",
                            "heading_breadcrumb": section.heading_breadcrumb,
                            "heading_text": section.heading_text,
                            "heading_level": section.heading_level,
                            "is_table": False,
                            "has_images": len(image_paths) > 0,
                            "image_paths": image_paths,
                            "document_type": "document",
                            "original_file": source,
                            "original_file_format": original_file_format,
                            "current_format": "text",
                            "uploaded_timestamp": uploaded_timestamp,
                            "content_type": "document_text",
                            "uniform_metadata_version": "1.0",
                        },
                    })

        return chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_docx_json(
        self,
        tree: List[Dict[str, Any]],
        *,
        doc_id: str,
        source: str = "",
        uploaded_timestamp: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Chunk a parsed DOCX heading tree.

        Args:
            tree: The hierarchical JSON list produced by
                  ``DocxParser.extract_docx_text()``.
            doc_id: Document-level identifier (e.g. filename stem).
            source: Path to the original ``.docx`` file.
            uploaded_timestamp: ISO timestamp.

        Returns:
            List of chunk dicts ready for indexing, each with heading
            breadcrumb metadata.
        """
        if not uploaded_timestamp:
            uploaded_timestamp = datetime.now().isoformat()

        original_file_format = ""
        if source:
            original_file_format = Path(source).suffix.lstrip(".").lower()

        # 1. Flatten the tree into leaf sections
        flat_sections = _flatten_tree(tree)
        logger.info(
            f"DOCX '{doc_id}': flattened heading tree → "
            f"{len(flat_sections)} sections"
        )

        # 2. Chunk each section
        all_chunks: List[Dict[str, Any]] = []
        for section in flat_sections:
            section_chunks = self._chunk_section_content(
                section,
                doc_id=doc_id,
                source=source,
                uploaded_timestamp=uploaded_timestamp,
                original_file_format=original_file_format,
                global_chunk_index=len(all_chunks),
            )
            all_chunks.extend(section_chunks)

        # 3. Re-index chunk_index + total_chunks uniformly
        for i, c in enumerate(all_chunks):
            c["chunk_index"] = i
            c["total_chunks"] = len(all_chunks)
            c["metadata"]["chunk_index"] = i
            c["metadata"]["total_chunks"] = len(all_chunks)

        logger.info(
            f"DOCX '{doc_id}': {len(flat_sections)} sections → "
            f"{len(all_chunks)} total chunks"
        )
        return all_chunks


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def chunk_docx_json(
    tree: List[Dict[str, Any]],
    *,
    doc_id: str = "docx_doc",
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
) -> List[Dict[str, Any]]:
    """
    One-call convenience to chunk parsed DOCX JSON output.

    Args:
        tree: Parsed JSON (hierarchical list from ``docx_reader_v2``).
        doc_id: Document identifier.
        source: Original file path.
        chunk_size: Max chunk size in characters.
        chunk_overlap: Overlap between text chunks.
        max_table_chunk_size: Max table chunk before row-by-row split.

    Returns:
        List of chunk dicts.
    """
    config = DocxChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    chunker = DocxTableChunker(config)
    return chunker.chunk_docx_json(tree, doc_id=doc_id, source=source)
