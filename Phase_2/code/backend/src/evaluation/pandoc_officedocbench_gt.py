"""Build OfficeDocBench-style ground truth from Pandoc native test files.

The converter intentionally maps only fields used by the current
OfficeDocBench scorer. Unsupported Pandoc nodes are traversed for text where
that helps existing metrics, but they do not create synthetic benchmark
features.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.evaluation.officedocbench_adapter import empty_officedocbench_output
from src.evaluation.parsing_info_loss.utils import normalize_text


_PANDOC_NATIVE_ARITY: Dict[str, int] = {
    # Blocks
    "Plain": 1,
    "Para": 1,
    "LineBlock": 1,
    "CodeBlock": 2,
    "RawBlock": 2,
    "BlockQuote": 1,
    "OrderedList": 2,
    "BulletList": 1,
    "DefinitionList": 1,
    "Header": 3,
    "HorizontalRule": 0,
    "Table": 6,
    "Figure": 3,
    "Div": 2,
    "Null": 0,
    # Inlines
    "Str": 1,
    "Emph": 1,
    "Underline": 1,
    "Strong": 1,
    "Strikeout": 1,
    "Superscript": 1,
    "Subscript": 1,
    "SmallCaps": 1,
    "Quoted": 2,
    "Cite": 2,
    "Code": 2,
    "Space": 0,
    "SoftBreak": 0,
    "LineBreak": 0,
    "Math": 2,
    "RawInline": 2,
    "Link": 3,
    "Image": 3,
    "Note": 1,
    "Span": 2,
    # Table internals
    "Caption": 2,
    "TableHead": 2,
    "TableBody": 4,
    "TableFoot": 2,
    "Row": 2,
    "Cell": 5,
    "RowSpan": 1,
    "ColSpan": 1,
    "ColWidth": 1,
    "RowHeadColumns": 1,
    # Common 0-arity values
    "Nothing": 0,
    "AlignDefault": 0,
    "AlignLeft": 0,
    "AlignRight": 0,
    "AlignCenter": 0,
    "ColWidthDefault": 0,
    "DefaultStyle": 0,
    "SingleQuote": 0,
    "DoubleQuote": 0,
    "DisplayMath": 0,
    "InlineMath": 0,
}


@dataclass(frozen=True)
class NativeNode:
    name: str
    args: Tuple[Any, ...] = ()


class _NativeParser:
    def __init__(self, text: str) -> None:
        self.tokens = _tokenize_native(text)
        self.index = 0

    def parse(self) -> Any:
        value = self._parse_expr()
        return value

    def _parse_expr(self) -> Any:
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of Pandoc native input")
        if token == "[":
            return self._parse_list()
        if token == "(":
            return self._parse_tuple()
        if token.startswith('"'):
            self.index += 1
            return _unescape_native_string(token)
        if re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", token):
            self.index += 1
            return float(token) if any(c in token for c in ".eE") else int(token)
        self.index += 1
        arity = _PANDOC_NATIVE_ARITY.get(token)
        if arity is None:
            return token
        args = tuple(self._parse_expr() for _ in range(arity))
        return NativeNode(token, args)

    def _parse_list(self) -> List[Any]:
        self._consume("[")
        items: List[Any] = []
        while self._peek() != "]":
            if self._peek() is None:
                raise ValueError("Unterminated Pandoc native list")
            items.append(self._parse_expr())
            if self._peek() == ",":
                self.index += 1
        self._consume("]")
        return items

    def _parse_tuple(self) -> Tuple[Any, ...]:
        self._consume("(")
        items: List[Any] = []
        while self._peek() != ")":
            if self._peek() is None:
                raise ValueError("Unterminated Pandoc native tuple")
            items.append(self._parse_expr())
            if self._peek() == ",":
                self.index += 1
        self._consume(")")
        return tuple(items)

    def _peek(self) -> Optional[str]:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def _consume(self, token: str) -> None:
        actual = self._peek()
        if actual != token:
            raise ValueError(f"Expected {token!r}, found {actual!r}")
        self.index += 1


def build_pandoc_officedocbench_gt(native_path: Path | str, *, file_format: str, source_path: Path | str | None = None) -> Dict[str, Any]:
    """Convert a Pandoc native file into OfficeDocBench-style GT."""

    native_file = Path(native_path)
    parsed = _NativeParser(native_file.read_text(encoding="utf-8")).parse()
    output = empty_officedocbench_output()
    _walk_blocks(_as_list(parsed), output, list_depth=0)
    _dedupe_generated_output(output)
    return output


def write_pandoc_officedocbench_gt(native_path: Path | str, output_path: Path | str, *, file_format: str, source_path: Path | str | None = None) -> Dict[str, Any]:
    gt = build_pandoc_officedocbench_gt(native_path, file_format=file_format, source_path=source_path)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    return gt


def discover_pandoc_docx_jobs(docx_dir: Path | str) -> List[Dict[str, Any]]:
    root = Path(docx_dir)
    jobs: List[Dict[str, Any]] = []
    for source_path in sorted(root.glob("*.docx")):
        native_path = source_path.with_suffix(".native")
        if native_path.exists():
            status = "OK" if _docx_has_default_document(source_path) else "UNSUPPORTED_SOURCE"
            jobs.append(
                {
                    "dataset": "pandoc-docx",
                    "format": "docx",
                    "file": source_path.name,
                    "doc_id": source_path.stem,
                    "source_path": str(source_path),
                    "native_path": str(native_path),
                    "status": status,
                }
            )
    return jobs


def discover_pandoc_pptx_jobs(pptx_dir: Path | str) -> List[Dict[str, Any]]:
    root = Path(pptx_dir)
    jobs: List[Dict[str, Any]] = []
    for case_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        native_path = case_dir / "input.native"
        source_path = case_dir / "output.pptx"
        if native_path.exists() and source_path.exists():
            jobs.append(
                {
                    "dataset": "pandoc-pptx",
                    "format": "pptx",
                    "file": f"{case_dir.name}/output.pptx",
                    "doc_id": case_dir.name,
                    "source_path": str(source_path),
                    "native_path": str(native_path),
                }
            )
    return jobs


def _docx_has_default_document(source_path: Path) -> bool:
    try:
        with zipfile.ZipFile(source_path) as zf:
            return "word/document.xml" in zf.namelist()
    except zipfile.BadZipFile:
        return False


def _walk_blocks(blocks: Sequence[Any], output: Dict[str, Any], *, list_depth: int) -> None:
    for block in blocks:
        if not isinstance(block, NativeNode):
            continue
        name = block.name
        if name in {"Plain", "Para"}:
            text = _inline_text(block.args[0], output)
            if text:
                output["text_elements"].append({"text": text, "style": ""})
        elif name == "Header":
            level = _coerce_int(block.args[0], 1)
            text = _inline_text(block.args[2], output)
            if text:
                output["headings"].append({"text": text, "level": max(1, min(level, 6))})
        elif name == "Table":
            rows, merge_count = _table_rows(block)
            if rows:
                output["tables"].append(_table_payload(rows, merge_count))
        elif name == "BulletList":
            _append_list(block.args[0], output, ordered=False, depth=list_depth + 1)
        elif name == "OrderedList":
            _append_list(block.args[1], output, ordered=True, depth=list_depth + 1)
        elif name == "BlockQuote":
            _walk_blocks(_as_list(block.args[0]), output, list_depth=list_depth)
        elif name == "Div":
            classes = _attr_classes(block.args[0])
            content = _as_list(block.args[1])
            if "notes" in classes:
                text = _blocks_text(content, output)
                if text:
                    output["speaker_notes"].append({"text": text})
            else:
                _walk_blocks(content, output, list_depth=list_depth)
        elif name == "Figure":
            _walk_blocks(_as_list(block.args[-1]), output, list_depth=list_depth)
        elif name == "CodeBlock":
            text = normalize_text(str(block.args[1]))
            if text:
                output["text_elements"].append({"text": text, "style": "code"})
        elif name in {"LineBlock", "DefinitionList"}:
            text = _generic_text(block, output)
            if text:
                output["text_elements"].append({"text": text, "style": ""})


def _append_list(items: Any, output: Dict[str, Any], *, ordered: bool, depth: int) -> None:
    list_items: List[str] = []
    for item in _as_list(items):
        blocks = _as_list(item)
        nested_blocks: List[Any] = []
        item_text_parts: List[str] = []
        for block in blocks:
            if isinstance(block, NativeNode) and block.name in {"BulletList", "OrderedList"}:
                nested_blocks.append(block)
            else:
                text = _block_text(block, output)
                if text:
                    item_text_parts.append(text)
        item_text = normalize_text(" ".join(item_text_parts))
        if item_text:
            list_items.append(item_text)
        _walk_blocks(nested_blocks, output, list_depth=depth)
    if list_items:
        output["lists"].append({"items": list_items, "ordered": ordered, "depth": depth})


def _block_text(block: Any, output: Dict[str, Any]) -> str:
    if isinstance(block, NativeNode):
        if block.name in {"Plain", "Para"}:
            return _inline_text(block.args[0], output)
        if block.name == "Header":
            return _inline_text(block.args[2], output)
        if block.name == "CodeBlock":
            return normalize_text(str(block.args[1]))
    return _generic_text(block, output)


def _blocks_text(blocks: Sequence[Any], output: Dict[str, Any]) -> str:
    return normalize_text(" ".join(text for text in (_block_text(block, output) for block in blocks) if text))


def _inline_text(value: Any, output: Dict[str, Any]) -> str:
    if isinstance(value, str):
        return "" if value in {"Space", "SoftBreak", "LineBreak"} else normalize_text(value)
    if isinstance(value, (int, float)):
        return normalize_text(str(value))
    if isinstance(value, list):
        return normalize_text("".join(_inline_piece(item, output) for item in value))
    if isinstance(value, tuple):
        return normalize_text(" ".join(_inline_text(item, output) for item in value))
    if isinstance(value, NativeNode):
        return normalize_text(_inline_piece(value, output))
    return ""


def _inline_piece(value: Any, output: Dict[str, Any]) -> str:
    if isinstance(value, NativeNode):
        name = value.name
        if name == "Str":
            return str(value.args[0])
        if name in {"Space", "SoftBreak", "LineBreak"}:
            return " "
        if name in {"Emph", "Underline", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps", "Span"}:
            return _inline_text(value.args[-1], output)
        if name == "Code":
            return str(value.args[1])
        if name in {"Math", "RawInline"}:
            return str(value.args[1])
        if name == "Quoted":
            return _inline_text(value.args[1], output)
        if name == "Cite":
            return _inline_text(value.args[1], output)
        if name == "Link":
            label = _inline_text(value.args[1], output)
            target = value.args[2] if len(value.args) > 2 else ("", "")
            url = normalize_text(str(target[0] if isinstance(target, tuple) and target else ""))
            if label or url:
                output["hyperlinks"].append({"text": label, "url": url})
            return label
        if name == "Image":
            label = _inline_text(value.args[1], output)
            target = value.args[2] if len(value.args) > 2 else ("", "")
            path = normalize_text(str(target[0] if isinstance(target, tuple) and target else ""))
            output["images"].append({"description": label, "path": path})
            return label
        if name == "Note":
            return ""
        return _generic_text(value, output)
    return _inline_text(value, output)


def _table_rows(table: NativeNode) -> Tuple[List[List[str]], int]:
    rows: List[List[str]] = []
    merge_count = 0
    for node in _iter_nodes(table):
        if isinstance(node, NativeNode) and node.name == "Row":
            row: List[str] = []
            for cell in _as_list(node.args[1]):
                if not isinstance(cell, NativeNode) or cell.name != "Cell":
                    continue
                rowspan = _span_value(cell.args[2])
                colspan = _span_value(cell.args[3])
                blocks = _as_list(cell.args[4])
                text = _cell_text(blocks)
                row.append(text)
                if rowspan > 1 or colspan > 1:
                    merge_count += max(rowspan * colspan - 1, 1)
            if row and any(cell for cell in row):
                rows.append(row)
    return rows, merge_count


def _cell_text(blocks: Sequence[Any]) -> str:
    scratch = empty_officedocbench_output()
    return _blocks_text(blocks, scratch)


def _table_payload(rows: Sequence[Sequence[str]], merge_count: int) -> Dict[str, Any]:
    normalized_rows = [[normalize_text(str(cell)) for cell in row] for row in rows if row]
    cell_text = normalize_text(" ".join(" ".join(row) for row in normalized_rows))
    payload: Dict[str, Any] = {
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "has_merged_cells": merge_count > 0,
        "cell_text": cell_text,
    }
    if merge_count:
        payload["merge_count"] = merge_count
    return payload


def _iter_nodes(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, NativeNode):
        for arg in value.args:
            yield from _iter_nodes(arg)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_nodes(item)


def _generic_text(value: Any, output: Dict[str, Any]) -> str:
    parts: List[str] = []
    for node in _iter_nodes(value):
        if isinstance(node, NativeNode):
            if node.name in {"Str", "Code", "Math", "RawInline"} and node.args:
                parts.append(str(node.args[-1]))
            elif node.name in {"Space", "SoftBreak", "LineBreak"}:
                parts.append(" ")
    return normalize_text(" ".join(parts))


def _attr_classes(attr: Any) -> List[str]:
    if not isinstance(attr, tuple) or len(attr) < 2:
        return []
    return [str(item) for item in _as_list(attr[1])]


def _span_value(value: Any) -> int:
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return _span_value(value[0])
    if isinstance(value, NativeNode) and value.args:
        return _coerce_int(value.args[0], 1)
    return 1


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return [value] if value is not None else []


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _dedupe_generated_output(output: Dict[str, Any]) -> None:
    for key in ("text_elements", "headings", "images", "lists", "hyperlinks", "speaker_notes"):
        seen = set()
        deduped = []
        for item in output.get(key, []):
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        output[key] = deduped


def _tokenize_native(text: str) -> List[str]:
    tokens: List[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if char in "[](),":
            tokens.append(char)
            i += 1
            continue
        if char == '"':
            start = i
            i += 1
            escaped = False
            while i < len(text):
                current = text[i]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    i += 1
                    break
                i += 1
            tokens.append(text[start:i])
            continue
        start = i
        while i < len(text) and (not text[i].isspace()) and text[i] not in "[](),":
            i += 1
        tokens.append(text[start:i])
    return tokens


def _unescape_native_string(token: str) -> str:
    inner = token[1:-1]

    def replace_numeric(match: re.Match[str]) -> str:
        try:
            return chr(int(match.group(1)))
        except Exception:
            return match.group(0)

    inner = re.sub(r"\\(\d+)", replace_numeric, inner)
    return (
        inner.replace(r"\"", '"')
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )
