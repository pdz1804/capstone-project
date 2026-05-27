"""
Born-Digital PDF Parser

Parses born-digital PDFs using pymupdf (fitz) to extract structured content
into the same heading-tree JSON format used by docx_reader_v2.py.

Output format:
[
  {
    "heading_text": "Chapter 1",
    "heading_level": 1,
    "content": "Body text...",
    "children": [...]
  }
]

Content strings may contain inline markers:
  [START_TABLE_CONTENT] ... [END_TABLE_CONTENT]
  [START_IMAGE_PATH] path|hash [END_IMAGE_PATH]

Heading detection uses three strategies (priority order):
  1. Tagged PDF structure tree (/StructTreeRoot)
  2. Table of Contents bookmarks (doc.get_toc())
  3. Font-based heuristics (size/bold analysis)
"""

import hashlib
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import fitz  # pymupdf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum image dimensions to extract (skip icons, bullets)
_MIN_IMG_WIDTH = 50
_MIN_IMG_HEIGHT = 50

# Skip images where this fraction (or more) of pixels are near-white.
# Catches decorative banners, header/footer strips, blank placeholders.
_MAX_WHITE_RATIO = 0.92
# Pixel channel threshold to consider "near-white" (0-255)
_WHITE_THRESHOLD = 240

# Minimum aspect-ratio guard: reject extremely wide/narrow strips
# (e.g. 1631×193 page-header decorations).  width/height > this → skip
_MAX_ASPECT_RATIO = 6.0

# Font size ratio above body text to consider as heading candidate
_HEADING_SIZE_RATIO = 1.2

# Maximum heading levels to detect
_MAX_HEADING_LEVELS = 6

# Table markers (same as docx_reader_v2)
TABLE_START = "[START_TABLE_CONTENT]"
TABLE_END = "[END_TABLE_CONTENT]"
IMG_START = "[START_IMAGE_PATH]"
IMG_END = "[END_IMAGE_PATH]"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class _SpanInfo:
    """A text span with font/position metadata."""

    text: str
    font: str
    size: float
    flags: int  # bold=16, italic=2, etc.
    bbox: Tuple[float, float, float, float]
    origin: Tuple[float, float]

    @property
    def is_bold(self) -> bool:
        return bool(self.flags & (1 << 4))  # bit 4 = bold

    @property
    def is_italic(self) -> bool:
        return bool(self.flags & (1 << 1))  # bit 1 = italic


@dataclass
class _ContentItem:
    """An extracted content item on a page (text, table, or image)."""

    kind: str  # "text", "heading", "table", "image"
    text: str = ""
    heading_level: int = 0
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    y_position: float = 0.0  # for ordering


@dataclass
class _FontProfile:
    """Aggregated font statistics for heading detection."""

    body_font: str = ""
    body_size: float = 0.0
    size_tiers: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


class PdfParser:
    """Parse a born-digital PDF into a heading-tree JSON structure."""

    def parse(
        self,
        file_path: str,
        output_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Parse a PDF file into a heading tree.

        Args:
            file_path: Path to the PDF file.
            output_dir: Directory to save extracted images.
                        If None, images are not extracted.

        Returns:
            List of heading-tree dicts (same format as docx_reader_v2).
        """
        file_path = Path(file_path)
        if output_dir:
            img_dir = Path(output_dir) / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
        else:
            img_dir = None

        doc = fitz.open(str(file_path))
        try:
            return self._parse_document(doc, img_dir)
        finally:
            doc.close()

    def _parse_document(
        self,
        doc: fitz.Document,
        img_dir: Optional[Path],
    ) -> List[Dict[str, Any]]:
        page_count = len(doc)
        if page_count == 0:
            return []

        # Step 1: Build font profile (scan all pages for body text font)
        font_profile = self._build_font_profile(doc)

        # Step 2: Build heading map from ToC and tagged structure
        toc_headings = self._build_toc_heading_map(doc)
        tag_headings = self._build_tagged_heading_map(doc)

        # Step 3: Extract content from each page
        all_items: List[_ContentItem] = []
        for page_idx in range(page_count):
            page = doc[page_idx]
            items = self._extract_page_content(
                doc, page, page_idx, font_profile, toc_headings, tag_headings, img_dir
            )
            all_items.extend(items)

        # Step 4: Build heading tree from flat content items
        tree = self._build_tree(all_items)

        # Step 5: Post-process tree
        self._normalize_heading_levels(tree)
        tree = self._prune_empty_nodes(tree)

        return tree

    # ------------------------------------------------------------------
    # Font profiling
    # ------------------------------------------------------------------

    def _build_font_profile(self, doc: fitz.Document) -> _FontProfile:
        """Scan document to find the most common (body) font and size."""
        size_counter: Counter = Counter()
        font_counter: Counter = Counter()

        # Sample up to 10 pages
        sample_pages = min(len(doc), 10)
        for i in range(sample_pages):
            page = doc[i]
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if len(text) < 3:
                            continue
                        size = round(span.get("size", 0), 1)
                        font = span.get("font", "")
                        char_count = len(text)
                        size_counter[size] += char_count
                        font_counter[font] += char_count

        if not size_counter:
            return _FontProfile()

        body_size = size_counter.most_common(1)[0][0]
        body_font = font_counter.most_common(1)[0][0] if font_counter else ""

        # Build size tiers for heading detection (distinct sizes above body)
        unique_sizes = sorted(
            {s for s, _ in size_counter.most_common() if s > body_size * _HEADING_SIZE_RATIO},
            reverse=True,
        )
        # Keep at most _MAX_HEADING_LEVELS tiers
        size_tiers = unique_sizes[:_MAX_HEADING_LEVELS]

        return _FontProfile(
            body_font=body_font,
            body_size=body_size,
            size_tiers=size_tiers,
        )

    # ------------------------------------------------------------------
    # Heading maps from ToC and tagged structure
    # ------------------------------------------------------------------

    def _build_toc_heading_map(
        self, doc: fitz.Document
    ) -> Dict[int, List[Tuple[int, str, float]]]:
        """Build a map of page_index -> [(level, title, y_position)] from ToC.

        ToC entries have [level, title, page_number]. We try to locate
        the title text on the target page to get a y position.
        """
        toc = doc.get_toc()
        if not toc:
            return {}

        heading_map: Dict[int, List[Tuple[int, str, float]]] = {}

        for level, title, page_num in toc:
            if page_num < 1 or page_num > len(doc):
                continue
            page_idx = page_num - 1
            page = doc[page_idx]

            # Try to find the title text on the page
            y_pos = 0.0
            title_clean = title.strip()
            if title_clean:
                search_results = page.search_for(title_clean)
                if search_results:
                    y_pos = search_results[0].y0

            if page_idx not in heading_map:
                heading_map[page_idx] = []
            heading_map[page_idx].append((level, title_clean, y_pos))

        # Sort by y position within each page
        for page_idx in heading_map:
            heading_map[page_idx].sort(key=lambda x: x[2])

        return heading_map

    def _build_tagged_heading_map(
        self, doc: fitz.Document
    ) -> Dict[int, List[Tuple[int, str, float]]]:
        """Build heading map from Tagged PDF structure tree.

        Looks for /S /H1 through /S /H6 structure elements.
        """
        try:
            cat_xref = doc.pdf_catalog()
            if cat_xref <= 0:
                return {}
            cat_str = doc.xref_object(cat_xref)
            if "/StructTreeRoot" not in cat_str:
                return {}
        except Exception:
            return {}

        # pymupdf doesn't have a high-level API for structure tree traversal
        # in all versions, so we skip this for now and rely on ToC + font heuristics.
        # This can be enhanced later when pymupdf exposes better structure tree APIs.
        return {}

    # ------------------------------------------------------------------
    # Page content extraction
    # ------------------------------------------------------------------

    def _extract_page_content(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_idx: int,
        font_profile: _FontProfile,
        toc_headings: Dict[int, List[Tuple[int, str, float]]],
        tag_headings: Dict[int, List[Tuple[int, str, float]]],
        img_dir: Optional[Path],
    ) -> List[_ContentItem]:
        """Extract all content items from a page, ordered by position."""
        items: List[_ContentItem] = []

        # --- Tables ---
        table_rects: List[fitz.Rect] = []
        try:
            tables = page.find_tables()
            for table in tables:
                rect = fitz.Rect(table.bbox)
                table_rects.append(rect)
                md_text = self._table_to_markdown(table)
                if md_text:
                    items.append(
                        _ContentItem(
                            kind="table",
                            text=f"{TABLE_START}\n{md_text}\n{TABLE_END}",
                            bbox=tuple(rect),
                            y_position=rect.y0,
                        )
                    )
        except Exception as e:
            logger.debug(f"Table extraction failed on page {page_idx}: {e}")

        # --- Images ---
        if img_dir:
            img_items = self._extract_images(doc, page, page_idx, img_dir)
            items.extend(img_items)

        # --- Text blocks ---
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        # Get heading info for this page
        page_toc = toc_headings.get(page_idx, [])
        page_tags = tag_headings.get(page_idx, [])

        # Detect columns
        columns = self._detect_columns(text_dict.get("blocks", []))

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # skip image blocks
                continue

            block_rect = fitz.Rect(block["bbox"])

            # Skip text inside table regions
            if self._rect_overlaps_any(block_rect, table_rects, threshold=0.5):
                continue

            block_text_parts = []
            block_heading_level = 0
            block_heading_text = ""

            for line in block.get("lines", []):
                line_text = ""
                line_spans: List[_SpanInfo] = []

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    si = _SpanInfo(
                        text=text,
                        font=span.get("font", ""),
                        size=round(span.get("size", 0), 1),
                        flags=span.get("flags", 0),
                        bbox=tuple(span.get("bbox", (0, 0, 0, 0))),
                        origin=tuple(span.get("origin", (0, 0))),
                    )
                    line_spans.append(si)
                    line_text += text

                line_text = line_text.strip()
                if not line_text:
                    continue

                # Check if this line is a heading
                heading_level = self._check_heading(
                    line_text, line_spans, block["bbox"],
                    page_toc, page_tags, font_profile,
                )

                if heading_level:
                    # If we already have accumulated text, flush it
                    if block_text_parts:
                        items.append(
                            _ContentItem(
                                kind="text",
                                text="\n".join(block_text_parts),
                                bbox=tuple(block_rect),
                                y_position=block_rect.y0,
                            )
                        )
                        block_text_parts = []

                    items.append(
                        _ContentItem(
                            kind="heading",
                            text=line_text,
                            heading_level=heading_level,
                            bbox=tuple(block_rect),
                            y_position=line["bbox"][1],
                        )
                    )
                else:
                    # Apply inline link formatting
                    enriched_line = self._apply_links(page, line, line_text)
                    block_text_parts.append(enriched_line)

            if block_text_parts:
                items.append(
                    _ContentItem(
                        kind="text",
                        text="\n".join(block_text_parts),
                        bbox=tuple(block_rect),
                        y_position=block_rect.y0,
                    )
                )

        # Sort all items by vertical position
        items.sort(key=lambda x: x.y_position)

        return items

    # ------------------------------------------------------------------
    # Heading detection
    # ------------------------------------------------------------------

    def _check_heading(
        self,
        line_text: str,
        spans: List[_SpanInfo],
        block_bbox: Tuple,
        page_toc: List[Tuple[int, str, float]],
        page_tags: List[Tuple[int, str, float]],
        font_profile: _FontProfile,
    ) -> int:
        """Check if a line of text is a heading. Returns level (1-6) or 0."""
        if not line_text.strip():
            return 0

        # Skip very long lines (unlikely to be headings)
        if len(line_text) > 200:
            return 0

        # Strategy 1: Match against Tagged PDF headings
        for level, title, y_pos in page_tags:
            if self._text_matches(line_text, title):
                return level

        # Strategy 2: Match against ToC entries
        for level, title, y_pos in page_toc:
            if self._text_matches(line_text, title):
                return min(level, _MAX_HEADING_LEVELS)

        # Strategy 3: Font-based heuristic
        return self._detect_heading_by_font(line_text, spans, font_profile)

    def _detect_heading_by_font(
        self,
        line_text: str,
        spans: List[_SpanInfo],
        font_profile: _FontProfile,
    ) -> int:
        """Detect heading level based on font size and boldness."""
        if not spans or font_profile.body_size <= 0:
            return 0

        # Get the dominant span properties
        total_chars = sum(len(s.text) for s in spans)
        if total_chars == 0:
            return 0

        # Weighted average size
        avg_size = sum(s.size * len(s.text) for s in spans) / total_chars
        is_bold = any(s.is_bold for s in spans if len(s.text.strip()) > 0)

        # Must be significantly larger than body text
        if avg_size < font_profile.body_size * _HEADING_SIZE_RATIO:
            # Check if it's bold + same size as body (sub-heading pattern)
            if is_bold and avg_size >= font_profile.body_size and len(line_text) < 100:
                # Bold text at body size → lowest heading level
                return _MAX_HEADING_LEVELS
            return 0

        # Map font size to heading level using size tiers
        if font_profile.size_tiers:
            for i, tier_size in enumerate(font_profile.size_tiers):
                if avg_size >= tier_size - 0.5:
                    return i + 1
            # Larger than body but not in any tier → last tier + 1
            return min(len(font_profile.size_tiers) + 1, _MAX_HEADING_LEVELS)

        # No tiers available   simple mapping
        ratio = avg_size / font_profile.body_size
        if ratio >= 2.0:
            return 1
        elif ratio >= 1.6:
            return 2
        elif ratio >= 1.3:
            return 3
        else:
            return 4

    def _text_matches(self, extracted: str, reference: str) -> bool:
        """Fuzzy match between extracted text and a reference heading title."""
        e = re.sub(r"\s+", " ", extracted.strip().lower())
        r = re.sub(r"\s+", " ", reference.strip().lower())
        if not r:
            return False
        # Exact match
        if e == r:
            return True
        # Prefix/contains match (ToC titles may be truncated)
        if len(r) > 5 and (e.startswith(r) or r.startswith(e)):
            return True
        # Check if one contains the other
        if len(r) > 10 and r in e:
            return True
        return False

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _table_to_markdown(self, table) -> str:
        """Convert a pymupdf table to Markdown format."""
        try:
            rows = table.extract()
        except Exception:
            return ""

        if not rows or len(rows) < 1:
            return ""

        # Clean cells
        cleaned_rows = []
        for row in rows:
            cleaned = []
            for cell in row:
                if cell is None:
                    cleaned.append("")
                else:
                    # Clean and escape pipe characters
                    text = str(cell).strip()
                    text = text.replace("|", "\\|")
                    text = text.replace("\n", "<br>")
                    cleaned.append(text)
            cleaned_rows.append(cleaned)

        if len(cleaned_rows) < 2:
            # Single row   not a useful table
            return ""

        # Build markdown table
        header = cleaned_rows[0]
        col_count = len(header)
        lines = []

        # Header row
        lines.append("| " + " | ".join(header) + " |")
        # Separator
        lines.append("| " + " | ".join(["---"] * col_count) + " |")
        # Data rows
        for row in cleaned_rows[1:]:
            # Pad or truncate to match column count
            while len(row) < col_count:
                row.append("")
            row = row[:col_count]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Image extraction
    # ------------------------------------------------------------------

    def _extract_images(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_idx: int,
        img_dir: Path,
    ) -> List[_ContentItem]:
        """Extract images from a page, save to disk, return content items with markers."""
        items = []
        images = page.get_images(full=True)

        seen_xrefs: Set[int] = set()
        img_counter = 0

        for img_info in images:
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                img_data = doc.extract_image(xref)
                if not img_data or not img_data.get("image"):
                    continue

                width = img_data.get("width", 0)
                height = img_data.get("height", 0)
                if width < _MIN_IMG_WIDTH or height < _MIN_IMG_HEIGHT:
                    continue

                # Skip extremely wide/narrow strips (header/footer decorations)
                aspect = max(width, height) / max(min(width, height), 1)
                if aspect > _MAX_ASPECT_RATIO:
                    logger.debug(
                        f"Skipping strip image xref={xref} on page {page_idx}: "
                        f"{width}x{height} aspect={aspect:.1f}"
                    )
                    continue

                ext = img_data.get("ext", "png")
                img_bytes = img_data["image"]

                # Skip near-white / blank images
                if self._is_blank_image(img_bytes, ext):
                    logger.debug(
                        f"Skipping blank image xref={xref} on page {page_idx}: "
                        f"{width}x{height}"
                    )
                    continue

                md5_hash = hashlib.md5(img_bytes).hexdigest()[:12]

                img_filename = f"img_{page_idx:03d}_{img_counter:02d}.{ext}"
                img_path = img_dir / img_filename
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                img_counter += 1

                # Get image position on page
                y_pos = 0.0
                try:
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        y_pos = img_rects[0].y0
                        bbox = tuple(img_rects[0])
                    else:
                        bbox = (0, 0, 0, 0)
                except Exception:
                    bbox = (0, 0, 0, 0)

                marker = f"{IMG_START} images/{img_filename}|{md5_hash} {IMG_END}"
                items.append(
                    _ContentItem(
                        kind="image",
                        text=marker,
                        bbox=bbox,
                        y_position=y_pos,
                    )
                )

            except Exception as e:
                logger.debug(f"Failed to extract image xref={xref} on page {page_idx}: {e}")

        return items

    @staticmethod
    def _is_blank_image(img_bytes: bytes, ext: str) -> bool:
        """Return True if the image is nearly all white (blank/decorative)."""
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            # Sample pixels for speed   full scan on small images,
            # down-sample large ones to ~100x100
            w, h = img.size
            if w * h > 20_000:
                img = img.resize((100, 100), Image.NEAREST)
            import numpy as np
            arr = np.asarray(img)
            white_pixels = np.all(arr > _WHITE_THRESHOLD, axis=2).sum()
            total_pixels = arr.shape[0] * arr.shape[1]
            ratio = white_pixels / total_pixels
            return ratio >= _MAX_WHITE_RATIO
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Link enrichment
    # ------------------------------------------------------------------

    def _apply_links(self, page: fitz.Page, line_dict: Dict, line_text: str) -> str:
        """Apply hyperlink formatting to a text line."""
        try:
            links = page.get_links()
        except Exception:
            return line_text

        if not links:
            return line_text

        line_rect = fitz.Rect(line_dict.get("bbox", (0, 0, 0, 0)))

        for link in links:
            if link.get("kind") != 2:  # kind 2 = URI
                continue
            uri = link.get("uri", "")
            if not uri:
                continue

            link_rect = fitz.Rect(link.get("from", (0, 0, 0, 0)))
            # Check if link overlaps with this line
            if not line_rect.intersects(link_rect):
                continue

            # Find the text spans that overlap with the link rect
            link_text = ""
            for span in line_dict.get("spans", []):
                span_rect = fitz.Rect(span.get("bbox", (0, 0, 0, 0)))
                if span_rect.intersects(link_rect):
                    link_text += span.get("text", "")

            link_text = link_text.strip()
            if link_text and link_text in line_text:
                # Replace first occurrence with markdown link
                line_text = line_text.replace(
                    link_text, f"[{link_text}]({uri})", 1
                )

        return line_text

    # ------------------------------------------------------------------
    # Column detection
    # ------------------------------------------------------------------

    def _detect_columns(
        self, blocks: List[Dict]
    ) -> List[Tuple[float, float]]:
        """Detect column layout from text block x-coordinates.

        Returns list of (x_start, x_end) ranges for detected columns.
        Currently informational   multi-column reordering is done by
        pymupdf's default block ordering which handles most cases.
        """
        if not blocks:
            return []

        text_blocks = [b for b in blocks if b.get("type") == 0]
        if len(text_blocks) < 4:
            return []

        # Collect left edges
        left_edges = [b["bbox"][0] for b in text_blocks]
        if not left_edges:
            return []

        # Simple gap detection: if blocks cluster into 2+ groups by x0
        left_edges.sort()
        gaps = []
        for i in range(1, len(left_edges)):
            gap = left_edges[i] - left_edges[i - 1]
            if gap > 50:  # significant horizontal gap
                gaps.append((left_edges[i - 1], left_edges[i]))

        # If no significant gaps, single column
        if not gaps:
            return [(min(left_edges), max(left_edges))]

        return gaps

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------

    def _build_tree(self, items: List[_ContentItem]) -> List[Dict[str, Any]]:
        """Build heading tree from flat content items.

        Uses the same stack-based algorithm as docx_reader_v2.py:
        - Heading → pop stack to level, create node, push
        - Text/table/image → append to current node's content
        """
        tree: List[Dict[str, Any]] = []
        stack: List[Tuple[int, Dict]] = []  # (level, node)

        for item in items:
            if item.kind == "heading" and item.heading_level > 0:
                node = {
                    "heading_text": item.text,
                    "heading_level": item.heading_level,
                    "children": [],
                }
                # Pop stack to find parent
                while stack and stack[-1][0] >= item.heading_level:
                    stack.pop()
                if stack:
                    stack[-1][1]["children"].append(node)
                else:
                    tree.append(node)
                stack.append((item.heading_level, node))

            else:
                # Content item (text, table, image)
                text = item.text
                if not text.strip():
                    continue

                if stack:
                    self._append_content(stack[-1][1], text)
                else:
                    # No heading yet   create implicit root
                    node = {
                        "heading_text": "",
                        "heading_level": 0,
                        "children": [],
                        "content": "",
                    }
                    tree.append(node)
                    stack.append((0, node))
                    self._append_content(node, text)

        return tree

    def _append_content(self, node: Dict, text: str) -> None:
        """Append text to a node's content field."""
        existing = node.get("content", "")
        if existing:
            node["content"] = existing + "\n" + text
        else:
            node["content"] = text

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _normalize_heading_levels(self, tree: List[Dict], parent_level: int = 0) -> None:
        """Ensure heading levels increase by 1 from parent (no gaps)."""
        for node in tree:
            current = node.get("heading_level", 0)
            expected = parent_level + 1
            if current > expected and parent_level > 0:
                node["heading_level"] = expected
            self._normalize_heading_levels(
                node.get("children", []), node["heading_level"]
            )

    def _prune_empty_nodes(self, tree: List[Dict]) -> List[Dict]:
        """Remove nodes with no content and no children (recursively)."""
        result = []
        for node in tree:
            node["children"] = self._prune_empty_nodes(node.get("children", []))
            has_content = bool(node.get("content", "").strip())
            has_children = bool(node.get("children"))
            if has_content or has_children:
                result.append(node)
        return result

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _rect_overlaps_any(
        rect: fitz.Rect,
        rects: List[fitz.Rect],
        threshold: float = 0.5,
    ) -> bool:
        """Check if rect overlaps significantly with any rect in the list."""
        rect_area = rect.width * rect.height
        if rect_area <= 0:
            return False
        for other in rects:
            intersection = rect & other
            if intersection.is_empty:
                continue
            overlap_area = intersection.width * intersection.height
            if overlap_area / rect_area >= threshold:
                return True
        return False


# ---------------------------------------------------------------------------
# Cross-page table merging (post-processing utility)
# ---------------------------------------------------------------------------


def merge_cross_page_tables(content: str) -> str:
    """Merge adjacent tables with matching column structure.

    If two consecutive TABLE_CONTENT blocks have the same number of columns
    and matching headers, merge them into a single table (dropping the
    duplicate header from the second table).

    Same logic as docx_reader_v2's table chaining.
    """
    parts = content.split(TABLE_START)
    if len(parts) <= 2:
        return content

    merged_parts = [parts[0]]
    prev_table = None
    prev_cols = None

    for part in parts[1:]:
        if TABLE_END not in part:
            merged_parts.append(TABLE_START + part)
            continue

        table_content, rest = part.split(TABLE_END, 1)
        table_lines = [l for l in table_content.strip().split("\n") if l.strip()]

        if len(table_lines) < 3:
            merged_parts.append(TABLE_START + part)
            prev_table = None
            prev_cols = None
            continue

        header_line = table_lines[0]
        cols = len(header_line.split("|")) - 2  # exclude leading/trailing empty

        # Check for merge with previous table
        between_text = rest.split(TABLE_START)[0].strip() if TABLE_START in rest else rest.strip()
        if (
            prev_table is not None
            and prev_cols == cols
            and not between_text
            and _headers_match(prev_table[0], header_line)
        ):
            # Merge: append data rows (skip header + separator)
            data_rows = table_lines[2:]
            prev_table.extend(data_rows)
        else:
            # Flush previous table if exists
            if prev_table is not None:
                merged_parts.append(
                    f"{TABLE_START}\n" + "\n".join(prev_table) + f"\n{TABLE_END}"
                )
            prev_table = table_lines
            prev_cols = cols

        # Keep the rest after this table
        if TABLE_START not in rest:
            if rest.strip():
                merged_parts.append(rest)

    # Flush last table
    if prev_table is not None:
        merged_parts.append(
            f"{TABLE_START}\n" + "\n".join(prev_table) + f"\n{TABLE_END}"
        )

    return "".join(merged_parts)


def _headers_match(header1: str, header2: str) -> bool:
    """Check if two markdown table header lines match."""
    h1 = [c.strip() for c in header1.split("|")]
    h2 = [c.strip() for c in header2.split("|")]
    return h1 == h2
