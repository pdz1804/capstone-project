#!/usr/bin/env python3
"""
Replace shared string indices in worksheet XML with actual string values.

    python rep_shared_str.py \
        --shared-strings parsed/excel/courseware/xl/sharedStrings.xml \
        --input parsed/excel/courseware/xl/worksheets/sheet1.xml \
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from typing import List
from pathlib import Path

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_NS = {"x": NS}


def extract_si_text(si: ET.Element) -> str:
    """Extract plain text from one <si> entry, including rich text runs."""
    # Shared strings can be either:
    # 1) <si><t>...</t></si>
    # 2) <si><r>...<t>...</t></r><r>...<t>...</t></r></si>
    parts: List[str] = []
    for t in si.findall(".//x:t", XML_NS):
        parts.append(t.text or "")
    return "".join(parts)


def load_shared_strings(shared_strings_path: str) -> List[str]:
    tree = ET.parse(shared_strings_path)
    root = tree.getroot()

    shared_values: List[str] = []
    for si in root.findall("x:si", XML_NS):
        shared_values.append(extract_si_text(si))

    return shared_values


def replace_indices_in_sheet(sheet_path: str, shared_values: List[str]) -> int:
    tree = ET.parse(sheet_path)
    root = tree.getroot()

    replaced_count = 0

    # Find all cells using shared strings: <c t="s"> <v>index</v> </c>
    for cell in root.findall(".//x:c[@t='s']", XML_NS):
        v_node = cell.find("x:v", XML_NS)
        if v_node is None or v_node.text is None:
            continue

        raw = v_node.text.strip()
        if not raw:
            continue

        try:
            idx = int(raw)
        except ValueError:
            continue

        if 0 <= idx < len(shared_values):
            v_node.text = shared_values[idx]
            replaced_count += 1
        else:
            print(
                f"[WARN] {sheet_path}: shared string index out of range: {idx}",
                file=sys.stderr,
            )

    # Keep the same namespace prefix behavior as ElementTree defaults.
    ET.register_namespace("", NS)

    sheet_path = Path(sheet_path)

    dest = str(sheet_path.with_name(f"{sheet_path.stem}.resolved{sheet_path.suffix}"))
    tree.write(dest, encoding="utf-8", xml_declaration=True)
    return replaced_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace shared string indices in a worksheet XML with actual string text."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to worksheet XML (e.g., xl/worksheets/sheet1.xml)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = os.path.abspath(args.input)
    input_path2 = Path(input_path)
    shared_path = str(input_path2.parent.parent / "sharedStrings.xml")

    if not os.path.exists(shared_path):
        print(f"[ERROR] sharedStrings.xml not found: {shared_path}", file=sys.stderr)
        return 1
    if not os.path.exists(input_path):
        print(f"[ERROR] input worksheet XML not found: {input_path}", file=sys.stderr)
        return 1

    shared_values = load_shared_strings(shared_path)
    replaced = replace_indices_in_sheet(input_path, shared_values)

    print(f"Done. Replaced {replaced} shared string indices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
