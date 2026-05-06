"""Utility functions for parsing information-loss evaluation."""

from __future__ import annotations

import html
import re
from difflib import SequenceMatcher
from typing import Iterable, List, Sequence, Tuple

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - optional dependency in some envs
    BeautifulSoup = None  # type: ignore


TABLE_START = "[START_TABLE_CONTENT]"
TABLE_END = "[END_TABLE_CONTENT]"
TABLE_START_ALT = "[START_TABLE]"
TABLE_END_ALT = "[END_TABLE]"
IMAGE_START = "[START_IMAGE_PATH]"
IMAGE_END = "[END_IMAGE_PATH]"

CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table|hình|bảng)\s*[\d.: -]", re.IGNORECASE)
HEADING_CANDIDATE_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,}\.?)\s+\S+")


def normalize_text(value: str) -> str:
    value = value or ""
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u00a0", " ")
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def text_similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a).lower()
    b_norm = normalize_text(b).lower()
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def token_f1(a: str, b: str) -> float:
    a_tokens = re.findall(r"[\w']+", normalize_text(a).lower(), flags=re.UNICODE)
    b_tokens = re.findall(r"[\w']+", normalize_text(b).lower(), flags=re.UNICODE)
    if not a_tokens and not b_tokens:
        return 1.0
    if not a_tokens or not b_tokens:
        return 0.0
    from collections import Counter

    ca = Counter(a_tokens)
    cb = Counter(b_tokens)
    overlap = sum((ca & cb).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(b_tokens)
    recall = overlap / len(a_tokens)
    return 2 * precision * recall / (precision + recall)


def combined_similarity(a: str, b: str) -> float:
    return 0.6 * token_f1(a, b) + 0.4 * text_similarity(a, b)


def parse_markdown_like_table(table_text: str) -> List[List[str]]:
    """Parse the table serialization embedded in parsed JSON content."""

    rows: List[List[str]] = []
    for raw_line in (table_text or "").splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("|"):
            continue
        cells = [normalize_text(cell) for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            continue
        rows.append(cells)
    return rows


def _collapse_horizontal_runs(row: Sequence[str]) -> List[Tuple[str, int]]:
    collapsed: List[Tuple[str, int]] = []
    i = 0
    while i < len(row):
        value = row[i]
        span = 1
        j = i + 1
        while j < len(row) and row[j] == value and value:
            span += 1
            j += 1
        collapsed.append((value, span))
        i = j
    return collapsed


def table_rows_to_html(rows: Sequence[Sequence[str]], recover_spans: bool = True) -> str:
    """Convert parsed table rows to compact canonical HTML.

    This intentionally performs conservative span recovery: contiguous duplicate
    non-empty cells in the same row become a colspan. It does not guess vertical
    spans unless the source builder already provides them.
    """

    out = ["<table>"]
    for row in rows:
        out.append("<tr>")
        cells = _collapse_horizontal_runs(row) if recover_spans else [(c, 1) for c in row]
        for value, colspan in cells:
            attr = f' colspan="{colspan}"' if colspan > 1 else ""
            out.append(f"<td{attr}>{html.escape(value)}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def html_to_text(html_value: str) -> str:
    if not html_value:
        return ""
    if BeautifulSoup is None:
        return re.sub(r"<[^>]+>", " ", html_value)
    soup = BeautifulSoup(html_value, "html.parser")
    return normalize_text(soup.get_text(" "))


def html_tree_tokens(html_value: str) -> List[str]:
    """Return a simple preorder token stream for table tree similarity."""

    if not html_value:
        return []
    if BeautifulSoup is None:
        tags = re.findall(r"</?([a-zA-Z0-9]+)(?:\s+[^>]*)?>", html_value)
        text = re.findall(r">([^<>]+)<", html_value)
        return tags + [normalize_text(t).lower() for t in text if normalize_text(t)]
    soup = BeautifulSoup(html_value, "html.parser")
    tokens: List[str] = []

    def walk(node) -> None:
        name = getattr(node, "name", None)
        if name:
            attrs = []
            for key in ("rowspan", "colspan"):
                if node.get(key):
                    attrs.append(f"{key}={node.get(key)}")
            tokens.append(name + ("[" + ",".join(attrs) + "]" if attrs else ""))
            for child in getattr(node, "children", []):
                walk(child)
            tokens.append("/" + name)
        else:
            text = normalize_text(str(node))
            if text:
                tokens.append(text.lower())

    table = soup.find("table") or soup
    walk(table)
    return tokens


def edit_similarity_from_tokens(a: Sequence[str], b: Sequence[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, list(a), list(b)).ratio()


def stable_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:06d}"


def average(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
