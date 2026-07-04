"""Normalize existing parsed JSON output into evaluation components."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .schemas import Component, DocumentComponents, SectionNode
from .utils import (
    CAPTION_RE,
    HEADING_CANDIDATE_RE,
    IMAGE_END,
    IMAGE_START,
    TABLE_END,
    TABLE_END_ALT,
    TABLE_START,
    TABLE_START_ALT,
    normalize_text,
    parse_markdown_like_table,
    stable_id,
    table_rows_to_html,
)


def load_prediction_json(path: Path, doc_id: str, modality: str) -> DocumentComponents:
    payload = json.loads(path.read_text(encoding="utf-8"))
    doc = DocumentComponents(
        doc_id=doc_id,
        modality=modality,
        source_path=str(path),
        reference_type="parsed_json",
        gt_strength="prediction",
    )
    order_counter = 0
    section_counter = 0
    component_counter = 0

    def next_order() -> int:
        nonlocal order_counter
        order_counter += 1
        return order_counter

    def add_component(
        component_type: str,
        *,
        text: str = "",
        html: str = "",
        media_path: str = "",
        scope_id: str,
        section_path: Sequence[str],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        nonlocal component_counter
        component_counter += 1
        doc.components.append(
            Component(
                id=stable_id("pred", component_counter),
                type=component_type,
                text=text,
                html=html,
                media_path=media_path,
                order=next_order(),
                scope_id=scope_id,
                section_path=list(section_path),
                meta=meta or {},
            )
        )

    def add_content_blocks(content: str, scope_id: str, section_path: Sequence[str]) -> None:
        pos = 0
        pattern = re.compile(
            rf"({re.escape(TABLE_START)}.*?{re.escape(TABLE_END)}|"
            rf"{re.escape(TABLE_START_ALT)}.*?{re.escape(TABLE_END_ALT)}|"
            rf"{re.escape(IMAGE_START)}.*?{re.escape(IMAGE_END)})",
            flags=re.DOTALL,
        )
        for match in pattern.finditer(content or ""):
            _add_text_and_markdown_tables(content[pos : match.start()], scope_id, section_path, add_component)
            block = match.group(0)
            if block.startswith(TABLE_START) or block.startswith(TABLE_START_ALT):
                if block.startswith(TABLE_START):
                    inner = block[len(TABLE_START) : -len(TABLE_END)].strip()
                else:
                    inner = block[len(TABLE_START_ALT) : -len(TABLE_END_ALT)].strip()
                rows = parse_markdown_like_table(inner)
                html = table_rows_to_html(rows, recover_spans=False)
                add_component(
                    "table",
                    text="\n".join(" | ".join(row) for row in rows),
                    html=html,
                    scope_id=scope_id,
                    section_path=section_path,
                    meta={"source_text": inner, "rows": rows},
                )
            else:
                inner = block[len(IMAGE_START) : -len(IMAGE_END)].strip()
                path_part = inner.split("|", 1)[0].strip()
                add_component("figure", media_path=path_part, scope_id=scope_id, section_path=section_path)
            pos = match.end()
        _add_text_and_markdown_tables(content[pos:], scope_id, section_path, add_component)

    def walk(nodes: Sequence[Dict[str, Any]], parent_id: Optional[str], path_parts: Sequence[str]) -> None:
        nonlocal section_counter
        for node in nodes:
            if not isinstance(node, dict):
                continue
            heading = normalize_text(str(_node_heading(node)))
            level = _coerce_int(node.get("heading_level"), 0)
            section_counter += 1
            section_id = stable_id("pred_sec", section_counter)
            section_path = list(path_parts) + ([heading] if heading else [])
            doc.sections.append(
                SectionNode(
                    id=section_id,
                    text=heading,
                    level=level,
                    parent_id=parent_id,
                    path=section_path,
                    order=next_order(),
                    scope_id=section_id,
                )
            )
            if heading:
                add_component(
                    "heading",
                    text=heading,
                    scope_id=section_id,
                    section_path=section_path,
                    meta={"level": level},
                )
            content = str(node.get("content", "") or "")
            add_content_blocks(content, section_id, section_path)
            children = node.get("children") or []
            if isinstance(children, list):
                walk(children, section_id, section_path)

    if isinstance(payload, list):
        walk(payload, None, [])
    elif isinstance(payload, dict):
        # Excel-like outputs may be a list in practice, but support dict forms.
        if "sheets" in payload and isinstance(payload["sheets"], list):
            walk(payload["sheets"], None, [])
        else:
            walk([payload], None, [])
    _add_derived_sections_from_headings(doc)
    return doc


def _add_derived_sections_from_headings(doc: DocumentComponents) -> None:
    existing = {normalize_text(section.text).lower() for section in doc.sections if normalize_text(section.text)}
    section_counter = len(doc.sections)
    for component in sorted((c for c in doc.components if c.type == "heading" and normalize_text(c.text)), key=lambda c: c.order):
        key = normalize_text(component.text).lower()
        if key in existing:
            continue
        existing.add(key)
        section_counter += 1
        level = _coerce_int(component.meta.get("level"), 1)
        section_id = stable_id("pred_sec", section_counter)
        doc.sections.append(
            SectionNode(
                id=section_id,
                text=component.text,
                level=level,
                parent_id=None,
                path=[component.text],
                order=component.order,
                scope_id=section_id,
            )
        )


def _add_text_and_markdown_tables(raw: str, scope_id: str, section_path: Sequence[str], add_component) -> None:
    lines = (raw or "").splitlines()
    text_buffer: List[str] = []
    i = 0

    def flush_text() -> None:
        if not text_buffer:
            return
        _add_text_lines("\n".join(text_buffer), scope_id, section_path, add_component)
        text_buffer.clear()

    while i < len(lines):
        if _is_markdown_table_start(lines, i):
            flush_text()
            table_lines = [lines[i]]
            i += 1
            while i < len(lines) and _is_markdown_table_row(lines[i]):
                table_lines.append(lines[i])
                i += 1
            table_text = "\n".join(table_lines)
            rows = parse_markdown_like_table(table_text)
            if rows:
                add_component(
                    "table",
                    text="\n".join(" | ".join(row) for row in rows),
                    html=table_rows_to_html(rows, recover_spans=False),
                    scope_id=scope_id,
                    section_path=section_path,
                    meta={"source_text": table_text, "rows": rows, "source_format": "markdown_pipe_table"},
                )
            continue

        text_buffer.append(lines[i])
        i += 1

    flush_text()


def _is_markdown_table_start(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return _is_markdown_table_row(lines[index]) and _is_markdown_table_separator(lines[index + 1])


def _is_markdown_table_row(line: str) -> bool:
    stripped = (line or "").strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_markdown_table_separator(line: str) -> bool:
    if not _is_markdown_table_row(line):
        return False
    cells = [cell.strip().replace(" ", "") for cell in line.strip().strip("|").split("|")]
    nonempty = [cell for cell in cells if cell]
    return bool(nonempty) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in nonempty)


def _add_text_lines(raw: str, scope_id: str, section_path: Sequence[str], add_component) -> None:
    buffer: List[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = normalize_text(" ".join(buffer))
        buffer.clear()
        if not text:
            return
        component_type = "caption" if CAPTION_RE.match(text) else "text"
        meta = {}
        if HEADING_CANDIDATE_RE.match(text):
            meta["implicit_heading_candidate"] = True
        add_component(component_type, text=text, scope_id=scope_id, section_path=section_path, meta=meta)

    for line in (raw or "").splitlines():
        stripped = normalize_text(line)
        if not stripped:
            flush()
            continue
        if CAPTION_RE.match(stripped) or HEADING_CANDIDATE_RE.match(stripped):
            flush()
            add_component(
                "caption" if CAPTION_RE.match(stripped) else "heading",
                text=stripped,
                scope_id=scope_id,
                section_path=section_path,
                meta={"implicit_heading_candidate": bool(HEADING_CANDIDATE_RE.match(stripped)), "level": _heading_level(stripped)},
            )
        else:
            buffer.append(stripped)
    flush()


def _node_heading(node: Dict[str, Any]) -> str:
    for key in ("heading_text", "sheet_name", "section", "title", "name"):
        value = str(node.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _heading_level(text: str) -> int:
    match = HEADING_CANDIDATE_RE.match(text or "")
    if not match:
        return 1
    return max(1, match.group(1).strip(".").count(".") + 1)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default
