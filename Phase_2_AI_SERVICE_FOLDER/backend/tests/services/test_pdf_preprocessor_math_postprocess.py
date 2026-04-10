"""Tests for PDF markdown math delimiter post-processing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chunking.pdf_preprocessor import PdfPreprocessor


def test_normalize_math_delimiters_inline_and_block() -> None:
    text = r"Inline \(a+b\) and display \[x^2 + y^2 = z^2\]."

    normalized = PdfPreprocessor._normalize_math_delimiters(text)

    assert normalized == "Inline $a+b$ and display $$x^2 + y^2 = z^2$$."


def test_normalize_tree_math_delimiters_recursive() -> None:
    tree = [
        {
            "heading_text": r"Section \(\alpha\)",
            "heading_level": 1,
            "content": r"Main \(x\) and \[y\]",
            "children": [
                {
                    "heading_text": "Child",
                    "heading_level": 2,
                    "content": r"Nested \(z\)",
                    "children": [],
                }
            ],
        }
    ]

    PdfPreprocessor._normalize_tree_math_delimiters(tree)

    assert tree[0]["heading_text"] == "Section $\\alpha$"
    assert tree[0]["content"] == "Main $x$ and $$y$$"
    assert tree[0]["children"][0]["content"] == "Nested $z$"
