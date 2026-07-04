"""Adapter from project parsed JSON into OfficeDocBench output schema."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from src.evaluation.parsing_info_loss.utils import (
    IMAGE_END,
    IMAGE_START,
    TABLE_END,
    TABLE_END_ALT,
    TABLE_START,
    TABLE_START_ALT,
    normalize_text,
    parse_markdown_like_table,
)


SHAPE_START = "[START_SHAPE_CONTENT]"
SHAPE_END = "[END_SHAPE_CONTENT]"
SHAPE_START_ALT = "[START_SHAPE]"
SHAPE_END_ALT = "[END_SHAPE]"
DIAGRAM_START = "[START_DIAGRAM]"
DIAGRAM_END = "[END_DIAGRAM]"
IMAGE_CONTENT_START = "[START_IMAGE_CONTENT]"
IMAGE_CONTENT_END = "[END_IMAGE_CONTENT]"

_TABLE_BLOCK_RE = re.compile(
    rf"({re.escape(TABLE_START)}.*?{re.escape(TABLE_END)}|"
    rf"{re.escape(TABLE_START_ALT)}.*?{re.escape(TABLE_END_ALT)})",
    flags=re.DOTALL,
)
_IMAGE_BLOCK_RE = re.compile(rf"{re.escape(IMAGE_START)}(.*?){re.escape(IMAGE_END)}", flags=re.DOTALL)
_SHAPE_BLOCK_RE = re.compile(
    rf"({re.escape(SHAPE_START)}.*?{re.escape(SHAPE_END)}|"
    rf"{re.escape(SHAPE_START_ALT)}.*?{re.escape(SHAPE_END_ALT)}|"
    rf"{re.escape(DIAGRAM_START)}.*?{re.escape(DIAGRAM_END)}|"
    rf"{re.escape(IMAGE_CONTENT_START)}.*?{re.escape(IMAGE_CONTENT_END)})",
    flags=re.DOTALL,
)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_ORDERED_RE = re.compile(r"^\s*\d+[.)]\s+(.+)")
_UNORDERED_RE = re.compile(r"^\s*[-*+]\s+(.+)")


def empty_officedocbench_output() -> Dict[str, Any]:
    """Return a complete OfficeDocBench adapter output shell."""

    return {
        "text_elements": [],
        "headings": [],
        "tables": [],
        "track_changes": [],
        "comments": [],
        "headers_footers": [],
        "footnotes": [],
        "speaker_notes": [],
        "text_boxes": [],
        "images": [],
        "lists": [],
        "hyperlinks": [],
        "bookmarks": [],
        "fields": [],
        "section_breaks": [],
        "metadata": {},
    }


def load_and_adapt_parsed_json(
    parsed_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
    source_path: Path | str | None = None,
    file_format: str | None = None,
) -> Dict[str, Any]:
    """Load project parsed JSON and convert it to OfficeDocBench schema."""

    parsed = json.loads(Path(parsed_path).read_text(encoding="utf-8"))
    metadata = _read_json_if_exists(metadata_path)
    return adapt_parsed_output(
        parsed,
        metadata=metadata,
        source_path=Path(source_path) if source_path else None,
        file_format=file_format,
    )


def adapt_parsed_output(
    parsed: Any,
    *,
    metadata: Dict[str, Any] | None = None,
    source_path: Path | None = None,
    file_format: str | None = None,
) -> Dict[str, Any]:
    """Convert project parser output to OfficeDocBench's flat adapter output.

    The production parser exports DOCX/PPTX as heading trees and XLSX as sheet
    dictionaries. This adapter preserves that production schema and emits the
    benchmark-specific shape only at evaluation time.
    """

    output = empty_officedocbench_output()
    fmt = (file_format or _infer_format(parsed, metadata, source_path)).lower()
    _add_metadata(output, parsed, metadata, source_path, fmt)

    # Handle new dict structure from docx_reader_v2.py with content_tree, bookmarks, track_changes
    if isinstance(parsed, dict):
        content_tree = parsed.get("content_tree", [])
        bookmarks = parsed.get("bookmarks", [])
        track_changes = parsed.get("track_changes", [])
        
        # Add bookmarks directly to output
        for bm in bookmarks:
            if isinstance(bm, dict) and "name" in bm:
                output["bookmarks"].append({"name": normalize_text(bm["name"])})
        
        # Add track changes directly to output
        for tc in track_changes:
            if isinstance(tc, dict):
                tc_data = {"type": tc.get("type", "")}
                if "author" in tc:
                    tc_data["author"] = normalize_text(tc["author"])
                if "text" in tc:
                    tc_data["text"] = normalize_text(tc["text"])
                output["track_changes"].append(tc_data)
        
        # Walk content tree for other elements
        _walk_content_nodes(content_tree, output)
    elif fmt in {"xlsx", "xlsm", "xls"} or _looks_like_sheet_list(parsed):
        _adapt_sheets(_coerce_list(parsed), output)
    else:
        _walk_content_nodes(_coerce_list(parsed), output)

    _dedupe_output(output)
    return output


def _adapt_sheets(sheets: Sequence[Any], output: Dict[str, Any]) -> None:
    sheet_names: List[str] = []
    for idx, sheet in enumerate(sheets, 1):
        if not isinstance(sheet, dict):
            text = normalize_text(str(sheet))
            if text:
                output["text_elements"].append({"text": text, "style": ""})
            continue
        name = normalize_text(str(sheet.get("sheet_name") or sheet.get("name") or sheet.get("title") or f"Sheet {idx}"))
        if name:
            sheet_names.append(name)
        content = str(sheet.get("content") or sheet.get("summary") or "")
        _adapt_content_text(content, output)
    if sheet_names:
        output.setdefault("metadata", {})["sheet_names"] = sheet_names


def _walk_content_nodes(nodes: Sequence[Any], output: Dict[str, Any]) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            text = normalize_text(str(node))
            if text:
                output["text_elements"].append({"text": text, "style": ""})
            continue

        heading = normalize_text(str(node.get("heading_text") or node.get("title") or node.get("heading") or ""))
        if heading:
            output["headings"].append({"text": heading, "level": _coerce_level(node.get("heading_level") or node.get("level"))})

        content = str(node.get("content") or "")
        if content:
            _adapt_content_text(content, output)

        # Extract bookmarks from node if present
        bookmarks = node.get("bookmarks")
        if isinstance(bookmarks, list):
            for bm in bookmarks:
                if isinstance(bm, dict) and "name" in bm:
                    output["bookmarks"].append({"name": normalize_text(bm["name"])})

        # Extract track changes from node if present
        track_changes = node.get("track_changes")
        if isinstance(track_changes, list):
            for tc in track_changes:
                if isinstance(tc, dict):
                    tc_data = {"type": tc.get("type", "")}
                    if "author" in tc:
                        tc_data["author"] = normalize_text(tc["author"])
                    if "text" in tc:
                        tc_data["text"] = normalize_text(tc["text"])
                    output["track_changes"].append(tc_data)

        children = node.get("children")
        if isinstance(children, list):
            _walk_content_nodes(children, output)


def _adapt_content_text(content: str, output: Dict[str, Any]) -> None:
    text_without_specials = content or ""

    for match in _TABLE_BLOCK_RE.finditer(content or ""):
        rows = _rows_from_table_block(match.group(0))
        _append_table(rows, output)
    text_without_specials = _TABLE_BLOCK_RE.sub("\n", text_without_specials)

    for match in _IMAGE_BLOCK_RE.finditer(content or ""):
        description = normalize_text(match.group(1).split("|", 1)[0])
        output["images"].append({"description": "" if description.upper() == "IMAGE" else description})
    text_without_specials = _IMAGE_BLOCK_RE.sub("\n", text_without_specials)

    for match in _SHAPE_BLOCK_RE.finditer(content or ""):
        shape_text = _strip_shape_markers(match.group(0))
        if shape_text and shape_text.upper() not in {"SHAPE", "DIAGRAM"}:
            output["text_boxes"].append({"text": shape_text})
    text_without_specials = _SHAPE_BLOCK_RE.sub("\n", text_without_specials)

    _append_markdown_tables_and_text(text_without_specials, output)


def _append_markdown_tables_and_text(text: str, output: Dict[str, Any]) -> None:
    lines = (text or "").splitlines()
    buffer: List[str] = []
    i = 0

    def flush_text() -> None:
        if not buffer:
            return
        _append_text_and_lists("\n".join(buffer), output)
        buffer.clear()

    while i < len(lines):
        if _is_markdown_table_start(lines, i):
            flush_text()
            table_lines = [lines[i]]
            i += 1
            while i < len(lines) and _is_markdown_table_row(lines[i]):
                table_lines.append(lines[i])
                i += 1
            _append_table(parse_markdown_like_table("\n".join(table_lines)), output)
            continue
        buffer.append(lines[i])
        i += 1

    flush_text()


def _append_text_and_lists(text: str, output: Dict[str, Any]) -> None:
    paragraphs: List[str] = []
    list_items: List[str] = []
    list_ordered: bool | None = None

    def flush_list() -> None:
        nonlocal list_items, list_ordered
        if list_items:
            output["lists"].append({"items": list_items, "ordered": bool(list_ordered)})
        list_items = []
        list_ordered = None

    def flush_paragraph() -> None:
        if paragraphs:
            paragraph = normalize_text(" ".join(paragraphs))
            if paragraph:
                output["text_elements"].append({"text": _strip_markdown_links(paragraph), "style": ""})
                _append_hyperlinks(paragraph, output)
            paragraphs.clear()

    for raw_line in (text or "").splitlines():
        line = normalize_text(raw_line)
        if not line:
            flush_paragraph()
            flush_list()
            continue
        ordered = _ORDERED_RE.match(line)
        unordered = _UNORDERED_RE.match(line)
        if ordered or unordered:
            flush_paragraph()
            item = normalize_text((ordered or unordered).group(1))
            current_ordered = bool(ordered)
            if list_ordered is not None and list_ordered != current_ordered:
                flush_list()
            list_ordered = current_ordered
            list_items.append(_strip_markdown_links(item))
            _append_hyperlinks(item, output)
            continue
        flush_list()
        paragraphs.append(line)

    flush_paragraph()
    flush_list()


def _append_table(rows: Sequence[Sequence[str]], output: Dict[str, Any]) -> None:
    normalized_rows = [[_strip_markdown_links(normalize_text(str(cell))) for cell in row] for row in rows if row]
    if not normalized_rows:
        return
    cell_text = normalize_text(" ".join(" ".join(row) for row in normalized_rows))
    has_merges, merge_count = _infer_merged_cells(normalized_rows)
    table = {
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "has_merged_cells": has_merges,
        "cell_text": cell_text,
    }
    if merge_count:
        table["merge_count"] = merge_count
    output["tables"].append(table)
    _append_hyperlinks("\n".join(" | ".join(row) for row in rows), output)


def _rows_from_table_block(block: str) -> List[List[str]]:
    if block.startswith(TABLE_START):
        inner = block[len(TABLE_START) : -len(TABLE_END)]
    else:
        inner = block[len(TABLE_START_ALT) : -len(TABLE_END_ALT)]
    return parse_markdown_like_table(inner)


def _infer_merged_cells(rows: Sequence[Sequence[str]]) -> Tuple[bool, int]:
    merge_count = 0
    for row in rows:
        previous = None
        run = 0
        for cell in row:
            value = normalize_text(str(cell))
            if value and value == previous:
                run += 1
            else:
                if run:
                    merge_count += run
                previous = value
                run = 0
        if run:
            merge_count += run
    return merge_count > 0, merge_count


def _append_hyperlinks(text: str, output: Dict[str, Any]) -> None:
    for label, url in _MD_LINK_RE.findall(text or ""):
        output["hyperlinks"].append({"text": normalize_text(label), "url": normalize_text(url)})


def _strip_markdown_links(text: str) -> str:
    return normalize_text(_MD_LINK_RE.sub(lambda m: m.group(1), text or ""))


def _strip_shape_markers(block: str) -> str:
    value = block
    for start, end in (
        (SHAPE_START, SHAPE_END),
        (SHAPE_START_ALT, SHAPE_END_ALT),
        (DIAGRAM_START, DIAGRAM_END),
        (IMAGE_CONTENT_START, IMAGE_CONTENT_END),
    ):
        if value.startswith(start):
            value = value[len(start) : -len(end)]
            break
    return normalize_text(value.replace("///", " "))


def _add_metadata(
    output: Dict[str, Any],
    parsed: Any,
    metadata: Dict[str, Any] | None,
    source_path: Path | None,
    fmt: str,
) -> None:
    meta = output.setdefault("metadata", {})
    if source_path:
        meta.setdefault("source_file", source_path.name)
    if metadata:
        for source_key, target_key in (
            ("title", "title"),
            ("author", "author"),
            ("created", "created"),
            ("modified", "modified"),
        ):
            if metadata.get(source_key):
                meta[target_key] = str(metadata[source_key])
    if fmt in {"xlsx", "xlsm", "xls"} and _looks_like_sheet_list(parsed):
        sheet_names = [
            normalize_text(str(sheet.get("sheet_name") or sheet.get("name") or ""))
            for sheet in _coerce_list(parsed)
            if isinstance(sheet, dict)
        ]
        sheet_names = [name for name in sheet_names if name]
        if sheet_names:
            meta["sheet_names"] = sheet_names


def _dedupe_output(output: Dict[str, Any]) -> None:
    for key in ("text_elements", "headings", "text_boxes", "images", "hyperlinks"):
        seen = set()
        deduped = []
        for item in output.get(key, []):
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        output[key] = deduped


def _infer_format(parsed: Any, metadata: Dict[str, Any] | None, source_path: Path | None) -> str:
    if source_path and source_path.suffix:
        return source_path.suffix.lower().lstrip(".")
    if metadata and metadata.get("file_type"):
        return str(metadata["file_type"]).lower().lstrip(".")
    if _looks_like_sheet_list(parsed):
        return "xlsx"
    return "docx"


def _looks_like_sheet_list(parsed: Any) -> bool:
    items = _coerce_list(parsed)
    return bool(items) and all(isinstance(item, dict) and ("sheet_name" in item or "name" in item) for item in items)


def _coerce_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("sheets"), list):
            return value["sheets"]
        return [value]
    return [value] if value is not None else []


def _coerce_level(value: Any) -> int:
    try:
        return max(1, min(int(value), 6))
    except Exception:
        return 1


def _is_markdown_table_start(lines: Sequence[str], index: int) -> bool:
    return index + 1 < len(lines) and _is_markdown_table_row(lines[index]) and _is_markdown_table_separator(lines[index + 1])


def _is_markdown_table_row(line: str) -> bool:
    stripped = (line or "").strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_markdown_table_separator(line: str) -> bool:
    if not _is_markdown_table_row(line):
        return False
    cells = [cell.strip().replace(" ", "") for cell in line.strip().strip("|").split("|")]
    nonempty = [cell for cell in cells if cell]
    return bool(nonempty) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in nonempty)


def _read_json_if_exists(path: Path | str | None) -> Dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
