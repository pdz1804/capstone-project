#!/usr/bin/env python3
"""
xlsx_reader_v2.py   Parse Excel (.xlsx / .xlsm) files from their raw XML
structure into a structured JSON representation.

Pipeline:
  1. Unzip raw Excel → parsed/excel/<hash>/
  2. Resolve shared-string indices in every worksheet XML
  3. Parse workbook metadata (sheets, defined names, rels)
  4. For each worksheet:
     a. Parse cell grid  (refs, types, values, formulas)
     b. Parse merged-cell regions and propagate values
     c. Parse XML-defined <table> elements (structured tables with headers)
     d. Parse hyperlinks (inline + relationship-based)
     e. Parse column widths and row heights
  5. Parse styles (number formats, fonts, fills, borders, alignment)
  6. Assemble per-workbook JSON → output/excel/<filename>.json
"""

# ──────────────────────────────────────────────────────────────────────
# §0 Preparation
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

try:
    from .rep_shared_str import load_shared_strings, replace_indices_in_sheet
except ImportError:
    from rep_shared_str import load_shared_strings, replace_indices_in_sheet

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw" / "excel"
PARSED_DIR = BASE_DIR / "parsed" / "excel"
OUTPUT_DIR = BASE_DIR / "output" / "excel"

# XML namespaces used in OOXML spreadsheets
NS_SPREADSHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_DRAWING_MAIN = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A   = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R   = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

XML_NS = {"x": NS_SPREADSHEET}

# Relationship type suffixes (the last segment of the full URI)
REL_TYPE_WORKSHEET = "relationships/worksheet"
REL_TYPE_CHARTSHEET = "relationships/chartsheet"
REL_TYPE_SHARED_STRINGS = "relationships/sharedStrings"
REL_TYPE_STYLES = "relationships/styles"
REL_TYPE_THEME = "relationships/theme"
REL_TYPE_TABLE = "relationships/table"
REL_TYPE_HYPERLINK = "relationships/hyperlink"
REL_TYPE_DRAWING = "relationships/drawing"
REL_TYPE_CHART = "relationships/chart"
REL_TYPE_EXTERNAL_LINK = "relationships/externalLink"
REL_TYPE_VBA = "relationships/vbaProject"

# Markers (consistent with docx_reader.py)
TABLE_START_MARKER = "[START_TABLE]"
TABLE_END_MARKER = "[END_TABLE]"
CHART_START_MARKER = "[START_CHART]"
CHART_END_MARKER = "[END_CHART]"
IMAGE_START_MARKER = "[START_IMAGE_PATH]"
IMAGE_END_MARKER   = "[END_IMAGE_PATH]"
SHAPE_START_MARKER = "[START_SHAPE]"
SHAPE_END_MARKER   = "[END_SHAPE]"
DIAGRAM_START_MARKER = "[START_DIAGRAM]"
DIAGRAM_END_MARKER   = "[END_DIAGRAM]"

# ──────────────────────────────────────────────────────────────────────
# §1  Cell-reference helpers
# ──────────────────────────────────────────────────────────────────────

_COL_RE = re.compile(r"^([A-Z]+)(\d+)$")

def col_letter_to_index(letters: str) -> int:
    """Convert column letters to 0-based index.  A→0, B→1, …, Z→25, AA→26."""
    result = 0
    for ch in letters:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def index_to_col_letter(idx: int) -> str:
    """Convert 0-based column index to letters.  0→A, 25→Z, 26→AA."""
    result: list[str] = []
    idx += 1  # 1-based
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result.append(chr(rem + ord("A")))
    return "".join(reversed(result))


def parse_cell_ref(ref: str) -> Tuple[int, int]:
    """Parse 'A1' → (row_0based, col_0based)."""
    m = _COL_RE.match(ref)
    if not m:
        raise ValueError(f"Invalid cell reference: {ref}")
    col = col_letter_to_index(m.group(1))
    row = int(m.group(2)) - 1
    return row, col


def parse_range_ref(range_ref: str) -> Tuple[int, int, int, int]:
    """Parse 'A1:C5' → (min_row, min_col, max_row, max_col) all 0-based."""
    # Strip any sheet name prefix like 'Sheet1!'
    if "!" in range_ref:
        range_ref = range_ref.split("!", 1)[1]
    # Remove any $ (absolute refs)
    range_ref = range_ref.replace("$", "")
    parts = range_ref.split(":")
    r1, c1 = parse_cell_ref(parts[0])
    if len(parts) == 2:
        r2, c2 = parse_cell_ref(parts[1])
    else:
        r2, c2 = r1, c1
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def cell_ref(row: int, col: int) -> str:
    """0-based (row, col) → 'A1'."""
    return f"{index_to_col_letter(col)}{row + 1}"


# ──────────────────────────────────────────────────────────────────────
# §2  Unzip raw Excel
# ──────────────────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    """Return md5 hex digest of a file (for deduplication of unzipped dirs)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def unzip_excel(excel_path: Path, dest_parent: Path = PARSED_DIR) -> Path:
    """
    Unzip an Excel file into dest_parent/<hash>/ and return the directory.
    Skips extraction if the directory already exists and is non-empty.
    """
    fhash = _file_hash(excel_path)
    dest = dest_parent / fhash
    if dest.exists() and any(dest.iterdir()):
        log.info("Already unzipped: %s → %s", excel_path.name, dest)
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    log.info("Unzipping %s → %s", excel_path.name, dest)
    with zipfile.ZipFile(excel_path, "r") as zf:
        zf.extractall(dest)
    return dest


# ──────────────────────────────────────────────────────────────────────
# §3  Shared-string resolution
# ──────────────────────────────────────────────────────────────────────

def resolve_shared_strings(parsed_dir: Path) -> List[str]:
    """
    Load shared strings and create .resolved.xml for every worksheet.
    Returns the shared-string list.
    """
    ss_path = parsed_dir / "xl" / "sharedStrings.xml"
    if not ss_path.exists():
        log.info("No sharedStrings.xml found in %s   skipping resolution", parsed_dir)
        return []

    shared_values = load_shared_strings(str(ss_path))
    log.info("Loaded %d shared strings from %s", len(shared_values), ss_path)

    ws_dir = parsed_dir / "xl" / "worksheets"
    if not ws_dir.exists():
        return shared_values

    for sheet_xml in sorted(ws_dir.glob("sheet*.xml")):
        # Skip already-resolved files
        if ".resolved" in sheet_xml.stem:
            continue
        resolved_path = sheet_xml.with_name(f"{sheet_xml.stem}.resolved{sheet_xml.suffix}")
        if resolved_path.exists():
            log.debug("Resolved file already exists: %s", resolved_path.name)
            continue
        count = replace_indices_in_sheet(str(sheet_xml), shared_values)
        log.info("Resolved %d shared-string refs in %s", count, sheet_xml.name)

    return shared_values


# ──────────────────────────────────────────────────────────────────────
# §4  Parse relationships (.rels) files
# ──────────────────────────────────────────────────────────────────────

def _parse_rels(rels_path: Path) -> Dict[str, Dict[str, str]]:
    """Parse a .rels XML file → {rId: {type_suffix, target, target_mode}}."""
    if not rels_path.exists():
        return {}
    tree = ET.parse(rels_path)
    root = tree.getroot()
    ns = {"r": NS_PACKAGE_REL}
    rels: Dict[str, Dict[str, str]] = {}
    for rel in root.findall("r:Relationship", ns):
        rid = rel.get("Id", "")
        rtype = rel.get("Type", "")
        target = rel.get("Target", "")
        target_mode = rel.get("TargetMode", "Internal")
        rels[rid] = {
            "type": rtype,
            "target": target,
            "target_mode": target_mode,
        }
    return rels


def _rel_type_matches(rel_type: str, suffix: str) -> bool:
    """Check if a relationship type URI ends with the given suffix."""
    return rel_type.endswith(suffix)


# ──────────────────────────────────────────────────────────────────────
# §5  Parse workbook metadata
# ──────────────────────────────────────────────────────────────────────

def parse_workbook(parsed_dir: Path) -> Dict[str, Any]:
    """
    Parse xl/workbook.xml + xl/_rels/workbook.xml.rels → structured metadata.
    Returns dict with keys: sheets, defined_names, file_version, calc_mode.
    """
    wb_path = parsed_dir / "xl" / "workbook.xml"
    rels_path = parsed_dir / "xl" / "_rels" / "workbook.xml.rels"

    rels = _parse_rels(rels_path)

    tree = ET.parse(wb_path)
    root = tree.getroot()

    # ── File version info ──
    fv = root.find("x:fileVersion", XML_NS)
    file_version: Dict[str, str] = {}
    if fv is not None:
        for attr in ("appName", "lastEdited", "lowestEdited", "rupBuild"):
            val = fv.get(attr)
            if val:
                file_version[attr] = val

    # ── Sheet list ──
    sheets: List[Dict[str, Any]] = []
    for s in root.findall(".//x:sheets/x:sheet", XML_NS):
        rid = s.get(f"{{{NS_REL}}}id", "")
        sheet_info: Dict[str, Any] = {
            "name": s.get("name", ""),
            "sheet_id": s.get("sheetId", ""),
            "state": s.get("state", "visible"),
            "r_id": rid,
        }
        # Resolve rId to file path
        if rid in rels:
            rel_type = rels[rid]["type"]
            if _rel_type_matches(rel_type, REL_TYPE_WORKSHEET):
                sheet_info["xml_path"] = rels[rid]["target"]  # e.g. "worksheets/sheet1.xml"
                sheet_info["sheet_type"] = "worksheet"
            elif _rel_type_matches(rel_type, REL_TYPE_CHARTSHEET):
                sheet_info["xml_path"] = rels[rid]["target"]  # e.g. "chartsheets/sheet1.xml"
                sheet_info["sheet_type"] = "chartsheet"
        sheets.append(sheet_info)

    # ── Defined names ──
    defined_names: List[Dict[str, str]] = []
    for dn in root.findall(".//x:definedNames/x:definedName", XML_NS):
        defined_names.append({
            "name": dn.get("name", ""),
            "value": (dn.text or "").strip(),
            "local_sheet_id": dn.get("localSheetId", ""),
        })

    # ── Categorize all rels ──
    wb_rels_summary: Dict[str, List[str]] = {}
    for rid, info in rels.items():
        rtype = info["type"].rsplit("/", 1)[-1]
        wb_rels_summary.setdefault(rtype, []).append(info["target"])

    return {
        "file_version": file_version,
        "sheets": sheets,
        "defined_names": defined_names,
        "rels_summary": wb_rels_summary,
    }


# ──────────────────────────────────────────────────────────────────────
# §6  Parse styles.xml
# ──────────────────────────────────────────────────────────────────────

def parse_styles(parsed_dir: Path) -> Dict[str, Any]:
    """
    Parse xl/styles.xml → number formats, fonts, fills, borders, cellXfs.
    Returns a lookup dict so we can later interpret cell style indices.
    """
    styles_path = parsed_dir / "xl" / "styles.xml"
    if not styles_path.exists():
        return {}

    tree = ET.parse(styles_path)
    root = tree.getroot()

    # ── Built-in number formats (subset) ──
    BUILTIN_NUM_FMTS: Dict[int, str] = {
        0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00",
        9: "0%", 10: "0.00%", 11: "0.00E+00", 12: "# ?/?", 13: "# ??/??",
        14: "mm-dd-yy", 15: "d-mmm-yy", 16: "d-mmm", 17: "mmm-yy",
        18: "h:mm AM/PM", 19: "h:mm:ss AM/PM", 20: "h:mm", 21: "h:mm:ss",
        22: "m/d/yy h:mm", 37: "#,##0 ;(#,##0)", 38: "#,##0 ;[Red](#,##0)",
        39: "#,##0.00;(#,##0.00)", 40: "#,##0.00;[Red](#,##0.00)",
        44: '_("$"* #,##0.00_)', 45: "mm:ss", 46: "[h]:mm:ss", 47: "mmss.0",
        48: "##0.0E+0", 49: "@",
    }

    # ── Custom number formats ──
    num_fmts: Dict[int, str] = dict(BUILTIN_NUM_FMTS)
    for nf in root.findall(".//x:numFmts/x:numFmt", XML_NS):
        nf_id = int(nf.get("numFmtId", "0"))
        nf_code = nf.get("formatCode", "General")
        num_fmts[nf_id] = nf_code

    # ── Fonts ──
    fonts: List[Dict[str, Any]] = []
    for font_el in root.findall(".//x:fonts/x:font", XML_NS):
        font_info: Dict[str, Any] = {}
        sz = font_el.find("x:sz", XML_NS)
        if sz is not None:
            font_info["size"] = float(sz.get("val", "11"))
        name = font_el.find("x:name", XML_NS)
        if name is not None:
            font_info["name"] = name.get("val", "")
        if font_el.find("x:b", XML_NS) is not None:
            font_info["bold"] = True
        if font_el.find("x:i", XML_NS) is not None:
            font_info["italic"] = True
        if font_el.find("x:u", XML_NS) is not None:
            font_info["underline"] = True
        color = font_el.find("x:color", XML_NS)
        if color is not None:
            font_info["color"] = color.get("rgb", color.get("theme", ""))
        fonts.append(font_info)

    # ── Fills ──
    fills: List[Dict[str, str]] = []
    for fill_el in root.findall(".//x:fills/x:fill", XML_NS):
        pf = fill_el.find("x:patternFill", XML_NS)
        fill_info: Dict[str, str] = {}
        if pf is not None:
            fill_info["pattern"] = pf.get("patternType", "none")
            fg = pf.find("x:fgColor", XML_NS)
            if fg is not None:
                fill_info["fg_color"] = fg.get("rgb", fg.get("theme", ""))
            bg = pf.find("x:bgColor", XML_NS)
            if bg is not None:
                fill_info["bg_color"] = bg.get("rgb", bg.get("theme", ""))
        fills.append(fill_info)

    # ── Borders ──
    borders: List[Dict[str, Any]] = []
    for brd_el in root.findall(".//x:borders/x:border", XML_NS):
        border_info: Dict[str, Any] = {}
        for side in ("left", "right", "top", "bottom", "diagonal"):
            side_el = brd_el.find(f"x:{side}", XML_NS)
            if side_el is not None and side_el.get("style"):
                border_info[side] = side_el.get("style", "")
        borders.append(border_info)

    # ── Cell XFs (the style records cells reference via s="N") ──
    cell_xfs: List[Dict[str, Any]] = []
    for xf_el in root.findall(".//x:cellXfs/x:xf", XML_NS):
        xf_info: Dict[str, Any] = {
            "num_fmt_id": int(xf_el.get("numFmtId", "0")),
            "font_id": int(xf_el.get("fontId", "0")),
            "fill_id": int(xf_el.get("fillId", "0")),
            "border_id": int(xf_el.get("borderId", "0")),
        }
        # Alignment
        align = xf_el.find("x:alignment", XML_NS)
        if align is not None:
            al: Dict[str, str] = {}
            for attr in ("horizontal", "vertical", "wrapText", "textRotation", "indent"):
                v = align.get(attr)
                if v:
                    al[attr] = v
            if al:
                xf_info["alignment"] = al
        cell_xfs.append(xf_info)

    return {
        "num_fmts": num_fmts,
        "fonts": fonts,
        "fills": fills,
        "borders": borders,
        "cell_xfs": cell_xfs,
    }


def _style_summary_for_cell(style_idx: int, styles: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact style summary dict for a cell given its style index."""
    if not styles or "cell_xfs" not in styles:
        return {}
    xfs = styles["cell_xfs"]
    if style_idx < 0 or style_idx >= len(xfs):
        return {}
    xf = xfs[style_idx]
    summary: Dict[str, Any] = {}

    # Number format
    nf_id = xf.get("num_fmt_id", 0)
    nf_map = styles.get("num_fmts", {})
    if nf_id in nf_map and nf_map[nf_id] != "General":
        summary["number_format"] = nf_map[nf_id]

    # Font
    fid = xf.get("font_id", 0)
    fonts = styles.get("fonts", [])
    if 0 <= fid < len(fonts):
        font = fonts[fid]
        if font.get("bold"):
            summary["bold"] = True
        if font.get("italic"):
            summary["italic"] = True
        if font.get("underline"):
            summary["underline"] = True

    # Fill
    fill_id = xf.get("fill_id", 0)
    fills_list = styles.get("fills", [])
    if 0 <= fill_id < len(fills_list):
        fill = fills_list[fill_id]
        if fill.get("pattern") not in ("none", "gray125", None, ""):
            summary["fill"] = fill.get("fg_color", fill.get("pattern", ""))

    # Alignment
    if "alignment" in xf:
        summary["alignment"] = xf["alignment"]

    return summary


# ──────────────────────────────────────────────────────────────────────
# §7  Parse a single worksheet XML
# ──────────────────────────────────────────────────────────────────────

def _parse_cell_element(cell_el: ET.Element, shared_values: List[str]) -> Dict[str, Any]:
    """
    Parse a single <c> element → dict with ref, value, type, formula, style_idx.
    Handles cell types: s (shared string), n (number), inlineStr, b (bool),
    e (error), str (formula-string), and the default (number).
    """
    ref = cell_el.get("r", "")
    cell_type = cell_el.get("t", "")  # s, n, inlineStr, b, e, str, or ""
    style_idx = int(cell_el.get("s", "0"))

    v_el = cell_el.find("x:v", XML_NS)
    f_el = cell_el.find("x:f", XML_NS)
    is_el = cell_el.find("x:is", XML_NS)  # inline string

    raw_value = v_el.text if v_el is not None and v_el.text else ""
    formula = f_el.text if f_el is not None and f_el.text else ""

    # Determine display value
    value: Any = ""
    value_type = "string"

    if cell_type == "s":
        # Shared string   use resolved text if available, else index
        try:
            idx = int(raw_value)
            if 0 <= idx < len(shared_values):
                value = shared_values[idx]
            else:
                value = raw_value
        except (ValueError, TypeError):
            value = raw_value
        value_type = "shared_string"

    elif cell_type == "inlineStr":
        # Inline string in <is><t>…</t></is>
        parts: List[str] = []
        if is_el is not None:
            for t_el in is_el.findall(".//x:t", XML_NS):
                parts.append(t_el.text or "")
        value = "".join(parts)
        value_type = "inline_string"

    elif cell_type == "b":
        if raw_value == "1":
            value = True
            value_type = "boolean"
        elif raw_value == "0":
            value = False
            value_type = "boolean"
        else:
            # Some workbooks emit boolean-typed cells without a cached value.
            # Treat those as empty instead of coercing them to False.
            value = ""
            value_type = "empty"

    elif cell_type == "e":
        value = raw_value  # e.g. "#REF!", "#N/A"
        value_type = "error"

    elif cell_type == "str":
        # Formula result cached as string
        value = raw_value
        value_type = "formula_string"

    elif cell_type in ("n", ""):
        # Number (explicit or default)
        if raw_value:
            try:
                if "." in raw_value or "E" in raw_value or "e" in raw_value:
                    value = float(raw_value)
                else:
                    value = int(raw_value)
            except ValueError:
                value = raw_value
            value_type = "number"
        else:
            value = ""
            value_type = "empty"
    else:
        value = raw_value
        value_type = cell_type

    cell_data: Dict[str, Any] = {"ref": ref, "value": value, "type": value_type}
    if formula:
        cell_data["formula"] = formula
    if style_idx:
        cell_data["style_idx"] = style_idx
    return cell_data


def parse_sheet(
    sheet_xml_path: Path,
    shared_values: List[str],
    sheet_rels_path: Optional[Path] = None,
    styles: Optional[Dict[str, Any]] = None,
    parsed_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Parse a single worksheet XML file into structured data.

    Returns dict with keys:
      - dimension: str (e.g. 'A1:L14')
      - columns: list of column width info
      - rows: dict[row_0based] → dict[col_0based] → cell_data
      - merged_cells: list of merge range dicts
      - hyperlinks: list of hyperlink dicts
      - tables: list of parsed table dicts (from xl/tables/)
      - row_count, col_count: bounding dimensions
    """
    tree = ET.parse(sheet_xml_path)
    root = tree.getroot()

    result: Dict[str, Any] = {}

    # ── Dimension ──
    dim_el = root.find("x:dimension", XML_NS)
    dimension_ref = dim_el.get("ref", "") if dim_el is not None else ""
    result["dimension"] = dimension_ref

    # ── Column definitions ──
    columns_info: List[Dict[str, Any]] = []
    for col_el in root.findall(".//x:cols/x:col", XML_NS):
        col_info: Dict[str, Any] = {
            "min": int(col_el.get("min", "1")),
            "max": int(col_el.get("max", "1")),
        }
        if col_el.get("width"):
            col_info["width"] = float(col_el.get("width", "8"))
        if col_el.get("customWidth") == "1":
            col_info["custom_width"] = True
        if col_el.get("hidden") == "1":
            col_info["hidden"] = True
        columns_info.append(col_info)
    result["columns"] = columns_info

    # ── Sheet data (cell grid) ──
    rows: Dict[int, Dict[int, Dict[str, Any]]] = {}
    max_row = 0
    max_col = 0
    for row_el in root.findall(".//x:sheetData/x:row", XML_NS):
        row_num = int(row_el.get("r", "0")) - 1  # 0-based
        row_height = row_el.get("ht")
        row_hidden = row_el.get("hidden") == "1"

        if row_num > max_row:
            max_row = row_num

        for cell_el in row_el.findall("x:c", XML_NS):
            cell_data = _parse_cell_element(cell_el, shared_values)
            ref = cell_data["ref"]
            try:
                r, c = parse_cell_ref(ref)
            except ValueError:
                continue
            if c > max_col:
                max_col = c

            # Add row metadata to the first cell in a row
            if row_height and c == 0:
                cell_data["row_height"] = float(row_height)
            if row_hidden:
                cell_data["row_hidden"] = True

            # Attach compact style info
            if styles and cell_data.get("style_idx"):
                style_info = _style_summary_for_cell(cell_data["style_idx"], styles)
                if style_info:
                    cell_data["style"] = style_info

            rows.setdefault(r, {})[c] = cell_data

    result["row_count"] = max_row + 1
    result["col_count"] = max_col + 1

    # ── Merged cells ──
    merged_cells: List[Dict[str, Any]] = []
    for mc_el in root.findall(".//x:mergeCells/x:mergeCell", XML_NS):
        mc_ref = mc_el.get("ref", "")
        if not mc_ref or ":" not in mc_ref:
            continue
        try:
            r1, c1, r2, c2 = parse_range_ref(mc_ref)
            merged_cells.append({
                "ref": mc_ref,
                "min_row": r1, "min_col": c1,
                "max_row": r2, "max_col": c2,
            })
        except (ValueError, IndexError):
            log.warning("Skipping invalid mergeCell ref: %s", mc_ref)
    result["merged_cells"] = merged_cells

    # Propagate merged-cell values: copy top-left cell value to all cells in range
    for mc in merged_cells:
        r1, c1, r2, c2 = mc["min_row"], mc["min_col"], mc["max_row"], mc["max_col"]
        # Find the value in the top-left cell
        src = rows.get(r1, {}).get(c1)
        if src is None:
            continue
        src_value = src.get("value", "")
        if not src_value and src_value != 0:
            continue
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                if rr == r1 and cc == c1:
                    continue  # skip the source cell itself
                if rr not in rows:
                    rows[rr] = {}
                if cc not in rows[rr]:
                    rows[rr][cc] = {
                        "ref": cell_ref(rr, cc),
                        "value": src_value,
                        "type": src.get("type", "string"),
                        "merged_from": src["ref"],
                    }
                else:
                    rows[rr][cc]["value"] = src_value
                    rows[rr][cc]["merged_from"] = src["ref"]

    result["rows"] = rows

    # ── Hyperlinks ──
    sheet_rels = _parse_rels(sheet_rels_path) if sheet_rels_path else {}
    hyperlinks: List[Dict[str, str]] = []
    for hl_el in root.findall(".//x:hyperlinks/x:hyperlink", XML_NS):
        hl: Dict[str, str] = {"ref": hl_el.get("ref", "")}
        rid = hl_el.get(f"{{{NS_REL}}}id", "")
        if rid and rid in sheet_rels:
            hl["url"] = sheet_rels[rid]["target"]
        display = hl_el.get("display", "")
        if display:
            hl["display"] = display
        location = hl_el.get("location", "")
        if location:
            hl["location"] = location
        hyperlinks.append(hl)
    result["hyperlinks"] = hyperlinks

    # Attach hyperlinks to their cells
    hyperlink_map: Dict[str, str] = {}
    for hl in hyperlinks:
        url = hl.get("url", hl.get("location", ""))
        if url and hl.get("ref"):
            hyperlink_map[hl["ref"]] = url
    for cell_ref_str, url in hyperlink_map.items():
        try:
            r, c = parse_cell_ref(cell_ref_str)
            if r in rows and c in rows[r]:
                rows[r][c]["hyperlink"] = url
        except ValueError:
            pass

    # ── Tables (XML-defined) ──
    tables: List[Dict[str, Any]] = []
    table_parts = root.findall(".//x:tableParts/x:tablePart", XML_NS)
    for tp_el in table_parts:
        tp_rid = tp_el.get(f"{{{NS_REL}}}id", "")
        if tp_rid and tp_rid in sheet_rels:
            table_rel_target = sheet_rels[tp_rid]["target"]
            # Resolve relative path: ../tables/table1.xml relative to worksheets/
            if parsed_dir is not None:
                table_xml_path = (parsed_dir / "xl" / "worksheets" / table_rel_target).resolve()
                if table_xml_path.exists():
                    table_data = _parse_table_xml(table_xml_path)
                    tables.append(table_data)
    result["tables"] = tables

    # ── Drawing references ──
    drawings: List[str] = []
    for draw_el in root.findall(".//x:drawing", XML_NS):
        draw_rid = draw_el.get(f"{{{NS_REL}}}id", "")
        if draw_rid and draw_rid in sheet_rels:
            drawings.append(sheet_rels[draw_rid]["target"])
    result["drawings"] = drawings

    return result


# ──────────────────────────────────────────────────────────────────────
# §8  Parse XML-defined tables
# ──────────────────────────────────────────────────────────────────────

def _parse_table_xml(table_xml_path: Path) -> Dict[str, Any]:
    """Parse xl/tables/tableN.xml → {name, display_name, ref, columns, ...}."""
    tree = ET.parse(table_xml_path)
    root = tree.getroot()

    table_data: Dict[str, Any] = {
        "id": root.get("id", ""),
        "name": root.get("name", ""),
        "display_name": root.get("displayName", ""),
        "ref": root.get("ref", ""),
        "header_row_count": int(root.get("headerRowCount", "1")),
        "totals_row_count": int(root.get("totalsRowCount", "0")),
    }

    # Table columns
    columns: List[Dict[str, str]] = []
    for tc_el in root.findall(".//x:tableColumns/x:tableColumn", XML_NS):
        columns.append({
            "id": tc_el.get("id", ""),
            "name": tc_el.get("name", ""),
        })
    table_data["columns"] = columns

    # Auto filter
    af_el = root.find("x:autoFilter", XML_NS)
    if af_el is not None:
        table_data["auto_filter_ref"] = af_el.get("ref", "")

    return table_data


# ──────────────────────────────────────────────────────────────────────
# §8.5  Parse drawing XML (shapes, images, diagrams)
# ──────────────────────────────────────────────────────────────────────
#
# Drawing objects live in xl/drawings/drawingN.xml.  Each sheet can
# reference one drawing via a <drawing r:id="…"/> element.
#
# Object types we handle:
#   - sp     (shape)     → [START_SHAPE]text///PresetType[END_SHAPE]
#   - pic    (picture)   → [START_IMAGE_PATH]path/to/media[END_IMAGE_PATH]
#   - cxnSp  (connector) → ignored (visual-only lines/arrows)
#   - grpSp  (group)     → [START_DIAGRAM]title///…shapes…[END_DIAGRAM]
#
# Positions are resolved from <xdr:from> (col/row based) and
# <a:off x="" y=""/> (absolute EMU).
# ──────────────────────────────────────────────────────────────────────

def _extract_shape_text(sp_el: ET.Element) -> str:
    """
    Extract all text content from a shape's <xdr:txBody> or <a:txBody>.
    Multiple paragraphs are joined with newlines.
    """
    parts: List[str] = []
    # Try both possible parent tags for txBody
    for txBody_tag in (f"{{{NS_XDR}}}txBody", f"{{{NS_A}}}txBody"):
        txBody = sp_el.find(txBody_tag)
        if txBody is not None:
            for p_el in txBody.findall(f"{{{NS_A}}}p"):
                runs: List[str] = []
                for r_el in p_el.findall(f"{{{NS_A}}}r"):
                    t_el = r_el.find(f"{{{NS_A}}}t")
                    if t_el is not None and t_el.text:
                        runs.append(t_el.text)
                if runs:
                    parts.append("".join(runs))
            break
    return "\n".join(parts)


def _get_prst_geom(sp_el: ET.Element) -> str:
    """Return the preset geometry name (e.g. 'rect', 'ellipse') or 'customShape'."""
    spPr = sp_el.find(f"{{{NS_XDR}}}spPr")
    if spPr is None:
        spPr = sp_el.find(f"{{{NS_A}}}spPr")
    if spPr is None:
        return "customShape"
    prst = spPr.find(f"{{{NS_A}}}prstGeom")
    if prst is not None:
        return prst.get("prst", "customShape")
    if spPr.find(f"{{{NS_A}}}custGeom") is not None:
        return "customShape"
    return "customShape"


def _get_shape_name(sp_el: ET.Element) -> str:
    """Return shape name from <xdr:nvSpPr>/<xdr:cNvPr name='...'> (or similar)."""
    for nv_tag in (f"{{{NS_XDR}}}nvSpPr", f"{{{NS_XDR}}}nvPicPr",
                   f"{{{NS_XDR}}}nvCxnSpPr", f"{{{NS_XDR}}}nvGrpSpPr"):
        nv = sp_el.find(nv_tag)
        if nv is not None:
            cnv = nv.find(f"{{{NS_XDR}}}cNvPr")
            if cnv is not None:
                return cnv.get("name", "")
    return ""


def _get_xfrm(el: ET.Element) -> Tuple[int, int, int, int]:
    """
    Extract (x, y, cx, cy) in EMU from an element's <a:xfrm>/<a:off>/<a:ext>.
    Searches inside <xdr:spPr>, <xdr:grpSpPr>, or directly under the element.
    Returns (0,0,0,0) if not found.
    """
    for container_tag in (f"{{{NS_XDR}}}spPr", f"{{{NS_XDR}}}grpSpPr",
                          f"{{{NS_A}}}spPr", f"{{{NS_A}}}grpSpPr", "."):
        container = el.find(container_tag) if container_tag != "." else el
        if container is None:
            continue
        xfrm = container.find(f"{{{NS_A}}}xfrm")
        if xfrm is not None:
            off = xfrm.find(f"{{{NS_A}}}off")
            ext = xfrm.find(f"{{{NS_A}}}ext")
            x = int(off.get("x", "0")) if off is not None else 0
            y = int(off.get("y", "0")) if off is not None else 0
            cx = int(ext.get("cx", "0")) if ext is not None else 0
            cy = int(ext.get("cy", "0")) if ext is not None else 0
            return x, y, cx, cy
    return 0, 0, 0, 0


def _get_anchor_row_col(anchor_el: ET.Element) -> Tuple[int, int]:
    """Return (row, col) from the <xdr:from> child of an anchor element."""
    from_el = anchor_el.find(f"{{{NS_XDR}}}from")
    if from_el is None:
        return 0, 0
    row_el = from_el.find(f"{{{NS_XDR}}}row")
    col_el = from_el.find(f"{{{NS_XDR}}}col")
    row = int(row_el.text) if row_el is not None and row_el.text else 0
    col = int(col_el.text) if col_el is not None and col_el.text else 0
    return row, col


def _parse_single_shape(sp_el: ET.Element) -> Dict[str, Any]:
    """Parse a single <xdr:sp> into a drawing-object dict."""
    name = _get_shape_name(sp_el)
    text = _extract_shape_text(sp_el)
    geom = _get_prst_geom(sp_el)
    x, y, cx, cy = _get_xfrm(sp_el)
    return {
        "kind": "shape",
        "name": name,
        "text": text,
        "geom": geom,
        "x": x, "y": y, "cx": cx, "cy": cy,
    }


def _parse_picture(pic_el: ET.Element, drawing_rels: Dict[str, Dict[str, str]],
                    parsed_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Parse a <xdr:pic> into a drawing-object dict."""
    name = _get_shape_name(pic_el)
    x, y, cx, cy = _get_xfrm(pic_el)

    # Get image path from blipFill → blip → r:embed
    image_path = ""
    blipFill = pic_el.find(f"{{{NS_XDR}}}blipFill")
    if blipFill is not None:
        blip = blipFill.find(f"{{{NS_A}}}blip")
        if blip is not None:
            embed_id = blip.get(f"{{{NS_R}}}embed", "")
            if embed_id and embed_id in drawing_rels:
                rel_target = drawing_rels[embed_id]["target"]
                # Resolve relative to xl/drawings/ → typically ../media/imageN.ext
                if parsed_dir is not None:
                    resolved = (parsed_dir / "xl" / "drawings" / rel_target).resolve()
                    image_path = str(resolved)
                else:
                    image_path = rel_target

    # Alt text / description
    descr = ""
    nvPicPr = pic_el.find(f"{{{NS_XDR}}}nvPicPr")
    if nvPicPr is not None:
        cnvPr = nvPicPr.find(f"{{{NS_XDR}}}cNvPr")
        if cnvPr is not None:
            descr = cnvPr.get("descr", "")

    return {
        "kind": "image",
        "name": name,
        "image_path": image_path,
        "descr": descr,
        "x": x, "y": y, "cx": cx, "cy": cy,
    }


def _parse_group_shape(
    grpSp_el: ET.Element,
    drawing_rels: Dict[str, Dict[str, str]],
    parsed_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Parse a <xdr:grpSp> into a diagram object.
    All child shapes are collected with their positions transformed
    to the group's coordinate space.
    """
    name = _get_shape_name(grpSp_el)

    # Group's own position and child coordinate space
    grpSpPr = grpSp_el.find(f"{{{NS_XDR}}}grpSpPr")
    gx, gy, gcx, gcy = 0, 0, 0, 0
    ch_off_x, ch_off_y, ch_ext_cx, ch_ext_cy = 0, 0, 0, 0
    if grpSpPr is not None:
        xfrm = grpSpPr.find(f"{{{NS_A}}}xfrm")
        if xfrm is not None:
            off = xfrm.find(f"{{{NS_A}}}off")
            ext = xfrm.find(f"{{{NS_A}}}ext")
            gx = int(off.get("x", "0")) if off is not None else 0
            gy = int(off.get("y", "0")) if off is not None else 0
            gcx = int(ext.get("cx", "0")) if ext is not None else 0
            gcy = int(ext.get("cy", "0")) if ext is not None else 0
            chOff = xfrm.find(f"{{{NS_A}}}chOff")
            chExt = xfrm.find(f"{{{NS_A}}}chExt")
            if chOff is not None:
                ch_off_x = int(chOff.get("x", "0"))
                ch_off_y = int(chOff.get("y", "0"))
            if chExt is not None:
                ch_ext_cx = int(chExt.get("cx", "1"))
                ch_ext_cy = int(chExt.get("cy", "1"))

    def _transform(cx: int, cy: int) -> Tuple[int, int]:
        """Transform child coords to sheet coords."""
        if ch_ext_cx and ch_ext_cy:
            sx = gx + (cx - ch_off_x) * gcx // ch_ext_cx
            sy = gy + (cy - ch_off_y) * gcy // ch_ext_cy
            return sx, sy
        return cx, cy

    # Collect child shapes (skip connectors)
    children: List[Dict[str, Any]] = []

    for child_sp in grpSp_el.findall(f"{{{NS_XDR}}}sp"):
        obj = _parse_single_shape(child_sp)
        obj["x"], obj["y"] = _transform(obj["x"], obj["y"])
        children.append(obj)

    for child_pic in grpSp_el.findall(f"{{{NS_XDR}}}pic"):
        obj = _parse_picture(child_pic, drawing_rels, parsed_dir)
        obj["x"], obj["y"] = _transform(obj["x"], obj["y"])
        children.append(obj)

    # Recursively handle nested groups
    for child_grp in grpSp_el.findall(f"{{{NS_XDR}}}grpSp"):
        obj = _parse_group_shape(child_grp, drawing_rels, parsed_dir)
        obj["x"], obj["y"] = _transform(obj["x"], obj["y"])
        children.append(obj)

    # Sort children left-to-right, top-to-bottom
    children.sort(key=lambda o: (o["y"], o["x"]))

    return {
        "kind": "diagram",
        "name": name,
        "children": children,
        "x": gx, "y": gy, "cx": gcx, "cy": gcy,
    }


# ──────────────────────────────────────────────────────────────────────
# §8.6  Parse chart XML (c:chartSpace)
# ──────────────────────────────────────────────────────────────────────

NS_CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"

# Known chart type tags (children of c:plotArea)
_CHART_TYPE_TAGS = [
    "barChart", "bar3DChart", "lineChart", "line3DChart",
    "pieChart", "pie3DChart", "doughnutChart",
    "areaChart", "area3DChart", "scatterChart", "bubbleChart",
    "radarChart", "surfaceChart", "surface3DChart",
    "stockChart", "ofPieChart",
]


def _extract_cached_points(ref_el: ET.Element) -> List[Tuple[int, str]]:
    """
    Extract cached data points from a <c:strRef> or <c:numRef> element.
    Returns list of (index, value) tuples sorted by index.
    """
    points: List[Tuple[int, str]] = []
    # Look for strCache or numCache
    for cache_tag in (f"{{{NS_CHART}}}strCache", f"{{{NS_CHART}}}numCache"):
        cache_el = ref_el.find(cache_tag)
        if cache_el is not None:
            for pt in cache_el.findall(f"{{{NS_CHART}}}pt"):
                idx = int(pt.get("idx", "0"))
                v_el = pt.find(f"{{{NS_CHART}}}v")
                val = v_el.text if v_el is not None and v_el.text else ""
                points.append((idx, val))
            break
    points.sort(key=lambda p: p[0])
    return points


def _parse_series(ser_el: ET.Element) -> Dict[str, Any]:
    """
    Parse a single <c:ser> element → dict with series name, categories, values.
    """
    series: Dict[str, Any] = {}

    # Series index / order
    idx_el = ser_el.find(f"{{{NS_CHART}}}idx")
    series["idx"] = int(idx_el.get("val", "0")) if idx_el is not None else 0

    # Series name (tx)
    tx_el = ser_el.find(f"{{{NS_CHART}}}tx")
    if tx_el is not None:
        # Try strRef first, then rich text
        str_ref = tx_el.find(f"{{{NS_CHART}}}strRef")
        if str_ref is not None:
            pts = _extract_cached_points(str_ref)
            if pts:
                series["name"] = pts[0][1]
        if "name" not in series:
            v_el = tx_el.find(f"{{{NS_CHART}}}v")
            if v_el is not None and v_el.text:
                series["name"] = v_el.text

    # Category labels (cat)
    cat_el = ser_el.find(f"{{{NS_CHART}}}cat")
    if cat_el is not None:
        for ref_tag in (f"{{{NS_CHART}}}strRef", f"{{{NS_CHART}}}numRef"):
            ref = cat_el.find(ref_tag)
            if ref is not None:
                pts = _extract_cached_points(ref)
                series["categories"] = [p[1] for p in pts]
                # Also capture the formula reference
                f_el = ref.find(f"{{{NS_CHART}}}f")
                if f_el is not None and f_el.text:
                    series["cat_ref"] = f_el.text
                break

    # Values (val)
    val_el = ser_el.find(f"{{{NS_CHART}}}val")
    if val_el is not None:
        for ref_tag in (f"{{{NS_CHART}}}numRef", f"{{{NS_CHART}}}strRef"):
            ref = val_el.find(ref_tag)
            if ref is not None:
                pts = _extract_cached_points(ref)
                series["values"] = [p[1] for p in pts]
                f_el = ref.find(f"{{{NS_CHART}}}f")
                if f_el is not None and f_el.text:
                    series["val_ref"] = f_el.text
                # Capture format code
                cache = ref.find(f"{{{NS_CHART}}}numCache")
                if cache is not None:
                    fmt_el = cache.find(f"{{{NS_CHART}}}formatCode")
                    if fmt_el is not None and fmt_el.text:
                        series["format_code"] = fmt_el.text
                break

    return series


def _extract_chart_title(chart_el: ET.Element) -> str:
    """Extract chart title text from <c:title>."""
    title_el = chart_el.find(f"{{{NS_CHART}}}title")
    if title_el is None:
        return ""

    # Try explicit rich text first: <c:tx><c:rich><a:p><a:r><a:t>
    tx = title_el.find(f"{{{NS_CHART}}}tx")
    if tx is not None:
        rich = tx.find(f"{{{NS_CHART}}}rich")
        if rich is not None:
            parts: List[str] = []
            for p_el in rich.findall(f"{{{NS_A}}}p"):
                runs: List[str] = []
                for r_el in p_el.findall(f"{{{NS_A}}}r"):
                    t_el = r_el.find(f"{{{NS_A}}}t")
                    if t_el is not None and t_el.text:
                        runs.append(t_el.text)
                if runs:
                    parts.append("".join(runs))
            if parts:
                return "\n".join(parts)

        # Try strRef
        str_ref = tx.find(f"{{{NS_CHART}}}strRef")
        if str_ref is not None:
            pts = _extract_cached_points(str_ref)
            if pts:
                return pts[0][1]

    return ""


def parse_chart_xml(chart_xml_path: Path) -> Dict[str, Any]:
    """
    Parse a chart XML file (xl/charts/chartN.xml) → structured chart data.

    Returns dict with keys:
      - title: str
      - chart_type: str (e.g. 'barChart', 'pieChart')
      - series: list of series dicts with name, categories, values
    """
    if not chart_xml_path.exists():
        return {}

    tree = ET.parse(chart_xml_path)
    root = tree.getroot()

    chart_data: Dict[str, Any] = {"source_file": chart_xml_path.name}

    # Find <c:chart> element
    chart_el = root.find(f"{{{NS_CHART}}}chart")
    if chart_el is None:
        log.warning("No <c:chart> element in %s", chart_xml_path)
        return chart_data

    # Title
    title = _extract_chart_title(chart_el)
    chart_data["title"] = title

    # Plot area → chart type and series
    plot_area = chart_el.find(f"{{{NS_CHART}}}plotArea")
    if plot_area is None:
        return chart_data

    # Find the chart type element
    chart_type = ""
    chart_type_el = None
    for ct_tag in _CHART_TYPE_TAGS:
        el = plot_area.find(f"{{{NS_CHART}}}{ct_tag}")
        if el is not None:
            chart_type = ct_tag
            chart_type_el = el
            break

    chart_data["chart_type"] = chart_type

    # Parse all series
    all_series: List[Dict[str, Any]] = []
    if chart_type_el is not None:
        for ser_el in chart_type_el.findall(f"{{{NS_CHART}}}ser"):
            s = _parse_series(ser_el)
            all_series.append(s)

    # Sort by series index
    all_series.sort(key=lambda s: s.get("idx", 0))
    chart_data["series"] = all_series

    log.info(
        "Parsed chart %s: type=%s, title='%s', %d series",
        chart_xml_path.name, chart_type, title, len(all_series),
    )
    return chart_data


def _format_chart_object(obj: Dict[str, Any]) -> str:
    """
    Format a chart drawing object into a readable marker-string representation.

    Output format:
      [START_CHART]
      <title>///<chart_type>
      [START_TABLE]
      | Category | SeriesName1 | SeriesName2 | ... |
      | --- | --- | ... |
      | cat1 | val1 | val2 | ... |
      ...
      [END_TABLE]
      [END_CHART]
    """
    chart = obj.get("chart_data", {})
    if not chart:
        return ""

    title = chart.get("title", "")
    chart_type = chart.get("chart_type", "chart")
    series_list = chart.get("series", [])

    lines: List[str] = [CHART_START_MARKER]
    if title:
        lines.append(f"{title}///{chart_type}")
    else:
        lines.append(f"///{chart_type}")
    
    if series_list:
        # Build a data table from the series
        # Determine categories from the first series that has them
        categories: List[str] = []
        for s in series_list:
            if s.get("categories"):
                categories = s["categories"]
                break

        # Build header: Category | Series1Name | Series2Name | ...
        series_names = [s.get("name", f"Series {s.get('idx', i)}") for i, s in enumerate(series_list)]

        if categories:
            header_cols = ["Category"] + series_names
        else:
            header_cols = series_names

        header = "| " + " | ".join(header_cols) + " |"
        sep = "| " + " | ".join(["---"] * len(header_cols)) + " |"

        lines.append(TABLE_START_MARKER)
        lines.append(header)
        lines.append(sep)

        if categories:
            max_rows = max(len(categories), max((len(s.get("values", [])) for s in series_list), default=0))
            for i in range(max_rows):
                cat = categories[i] if i < len(categories) else ""
                vals = []
                for s in series_list:
                    sv = s.get("values", [])
                    vals.append(sv[i] if i < len(sv) else "")
                row = "| " + " | ".join([str(cat)] + [str(v) for v in vals]) + " |"
                lines.append(row)
        else:
            # No categories   just output values
            max_rows = max((len(s.get("values", [])) for s in series_list), default=0)
            for i in range(max_rows):
                vals = []
                for s in series_list:
                    sv = s.get("values", [])
                    vals.append(sv[i] if i < len(sv) else "")
                row = "| " + " | ".join([str(v) for v in vals]) + " |"
                lines.append(row)

        lines.append(TABLE_END_MARKER)

    lines.append(CHART_END_MARKER)
    return "\n".join(lines)


def _parse_graphic_frame(
    gf_el: ET.Element,
    drawing_rels: Dict[str, Dict[str, str]],
    parsed_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parse a <xdr:graphicFrame> element.  If it contains an embedded chart
    reference, resolve and parse the chart XML.  Returns a chart drawing
    object dict or None if no chart is found.
    """
    # Get frame name
    name = ""
    nvGfPr = gf_el.find(f"{{{NS_XDR}}}nvGraphicFramePr")
    if nvGfPr is not None:
        cnvPr = nvGfPr.find(f"{{{NS_XDR}}}cNvPr")
        if cnvPr is not None:
            name = cnvPr.get("name", "")

    # Get position from xfrm
    xfrm_el = gf_el.find(f"{{{NS_XDR}}}xfrm")
    x, y = 0, 0
    if xfrm_el is not None:
        off = xfrm_el.find(f"{{{NS_A}}}off")
        if off is not None:
            x = int(off.get("x", "0"))
            y = int(off.get("y", "0"))

    # Look for chart reference inside <a:graphic><a:graphicData><c:chart r:id="..."/>
    graphic = gf_el.find(f"{{{NS_A}}}graphic")
    if graphic is None:
        return None

    graphic_data = graphic.find(f"{{{NS_A}}}graphicData")
    if graphic_data is None:
        return None

    # Check if the graphicData URI indicates a chart
    uri = graphic_data.get("uri", "")
    if "chart" not in uri:
        return None

    # Find the chart element   it uses the chart namespace
    chart_ref_el = graphic_data.find(f"{{{NS_CHART}}}chart")
    if chart_ref_el is None:
        return None

    chart_rid = chart_ref_el.get(f"{{{NS_R}}}id", "")
    if not chart_rid or chart_rid not in drawing_rels:
        log.warning("Chart rId '%s' not found in drawing rels", chart_rid)
        return None

    rel_info = drawing_rels[chart_rid]
    chart_target = rel_info["target"]  # e.g. "../charts/chart1.xml"

    # Resolve chart path relative to the drawing's directory
    chart_xml_path: Optional[Path] = None
    if parsed_dir is not None:
        # Try relative to xl/drawings/
        chart_xml_path = (parsed_dir / "xl" / "drawings" / chart_target).resolve()
        if not chart_xml_path.exists():
            chart_xml_path = (parsed_dir / "xl" / chart_target.lstrip("/")).resolve()
        if not chart_xml_path.exists():
            # Manual ../  resolution
            parts = chart_target.replace("\\", "/").split("/")
            resolved = parsed_dir / "xl" / "drawings"
            for p in parts:
                if p == "..":
                    resolved = resolved.parent
                else:
                    resolved = resolved / p
            chart_xml_path = resolved.resolve()

    if chart_xml_path is None or not chart_xml_path.exists():
        log.warning("Chart XML not found: %s", chart_target)
        return None

    chart_data = parse_chart_xml(chart_xml_path)

    return {
        "kind": "chart",
        "name": name,
        "chart_data": chart_data,
        "x": x, "y": y, "cx": 0, "cy": 0,
    }

# Helper function for ordering non-text drawing objects

def _order_drawing_objects_reading_order(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Human-ish reading order for floating drawing objects (charts/images/shapes):
    - cluster into visual rows using a Y tolerance
    - within each row, sort left-to-right
    - tie-breaker: XML/serialization order (seq) for stability

    Expects each object may have: x, y, cx, cy.
    """
    if not objects:
        return objects

    # Stable tie-breaker: original serialization order in drawingX.xml
    # (your list is built by iterating anchor_el elements in document order)
    for i, o in enumerate(objects):
        o["_seq"] = i

    # Build geometry features
    items = []
    heights = []
    for o in objects:
        x = int(o.get("x", 0) or 0)
        y = int(o.get("y", 0) or 0)
        cx = int(o.get("cx", 0) or 0)
        cy = int(o.get("cy", 0) or 0)

        # If cy is missing/0 (some objects), give a tiny fallback so y_center exists
        h = cy if cy > 0 else 1
        y_center = y + h / 2.0

        items.append((o, x, y, cx, cy, y_center, h))
        if cy > 0:
            heights.append(cy)

    # Dynamic tolerance so small vertical drift doesn't split a row
    heights.sort()
    if heights:
        mid = len(heights) // 2
        median_h = heights[mid] if len(heights) % 2 == 1 else (heights[mid - 1] + heights[mid]) / 2.0
    else:
        median_h = 1.0

    tol_y = max(1.0, 0.25 * float(median_h))  # 25% of typical object height

    # Row clustering by y_center
    items.sort(key=lambda t: (t[5], t[1], t[0].get("_seq", 0)))  # sort by y_center then x

    rows: List[Dict[str, Any]] = []
    current = None

    for (o, x, y, cx, cy, y_center, h) in items:
        if current is None:
            current = {"y_centers": [y_center], "items": [(o, x, y, cx, cy, y_center)]}
            continue

        row_mean = sum(current["y_centers"]) / len(current["y_centers"])
        if abs(y_center - row_mean) <= tol_y:
            current["y_centers"].append(y_center)
            current["items"].append((o, x, y, cx, cy, y_center))
        else:
            rows.append(current)
            current = {"y_centers": [y_center], "items": [(o, x, y, cx, cy, y_center)]}

    if current is not None:
        rows.append(current)

    # Sort rows top-to-bottom, then items left-to-right within each row.
    # Tie-breaker for near-identical x: seq (XML order)
    rows.sort(key=lambda r: sum(r["y_centers"]) / len(r["y_centers"]))

    ordered: List[Dict[str, Any]] = []
    for r in rows:
        r["items"].sort(key=lambda t: (t[1], t[2], t[0].get("_seq", 0)))  # x, then y, then seq
        for (o, *_rest) in r["items"]:
            ordered.append(o)

    # Clean up internal key
    for o in ordered:
        o.pop("_seq", None)

    return ordered

def parse_drawing(
    drawing_xml_path: Path,
    parsed_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Parse a drawingN.xml file → list of positioned drawing objects.

    Each object is a dict with at minimum:
        kind:  "shape" | "image" | "diagram"
        x, y:  absolute EMU position
        row, col:  cell-anchor position (from <xdr:from>)
        ...kind-specific keys...
    """
    if not drawing_xml_path.exists():
        return []

    # Load drawing rels (for image references)
    rels_path = drawing_xml_path.parent / "_rels" / f"{drawing_xml_path.name}.rels"
    drawing_rels = _parse_rels(rels_path)

    tree = ET.parse(drawing_xml_path)
    root = tree.getroot()

    objects: List[Dict[str, Any]] = []

    # Process all anchor types
    for anchor_tag in (f"{{{NS_XDR}}}twoCellAnchor",
                       f"{{{NS_XDR}}}oneCellAnchor",
                       f"{{{NS_XDR}}}absoluteAnchor"):
        for anchor_el in root.findall(anchor_tag):
            anchor_row, anchor_col = _get_anchor_row_col(anchor_el)

            # ── Shape ──
            for sp_el in anchor_el.findall(f"{{{NS_XDR}}}sp"):
                obj = _parse_single_shape(sp_el)
                obj["row"] = anchor_row
                obj["col"] = anchor_col
                objects.append(obj)

            # ── Picture ──
            for pic_el in anchor_el.findall(f"{{{NS_XDR}}}pic"):
                obj = _parse_picture(pic_el, drawing_rels, parsed_dir)
                obj["row"] = anchor_row
                obj["col"] = anchor_col
                objects.append(obj)

            # ── Group shape → diagram ──
            for grp_el in anchor_el.findall(f"{{{NS_XDR}}}grpSp"):
                obj = _parse_group_shape(grp_el, drawing_rels, parsed_dir)
                obj["row"] = anchor_row
                obj["col"] = anchor_col
                objects.append(obj)

            # ── Graphic frame → chart ──
            for gf_el in anchor_el.findall(f"{{{NS_XDR}}}graphicFrame"):
                obj = _parse_graphic_frame(gf_el, drawing_rels, parsed_dir)
                if obj is not None:
                    obj["row"] = anchor_row
                    obj["col"] = anchor_col
                    objects.append(obj)

            # ── Connectors (cxnSp) are intentionally skipped ──

    # Sort all objects by position: top-to-bottom, left-to-right (deprecated)
    # objects.sort(key=lambda o: (o.get("y", 0), o.get("x", 0)))

    # Ordering drawing objects
    objects = _order_drawing_objects_reading_order(objects)

    log.info(
        "Parsed drawing %s: %d objects (%s)",
        drawing_xml_path.name,
        len(objects),
        ", ".join(f"{o['kind']}" for o in objects[:5]) + ("..." if len(objects) > 5 else ""),
    )
    return objects


def _format_drawing_object(obj: Dict[str, Any]) -> str:
    """
    Format a single drawing object into its marker-string representation.
    """
    kind = obj.get("kind", "")

    if kind == "image":
        path = obj.get("image_path", "")
        return f"{IMAGE_START_MARKER} {path} {IMAGE_END_MARKER}"

    elif kind == "shape":
        text = obj.get("text", "").strip()
        geom = obj.get("geom", "customShape")
        # Capitalize geometry name: rect → Rect, ellipse → Ellipse
        geom_display = geom[0].upper() + geom[1:] if geom else "Shape"
        return f"{SHAPE_START_MARKER}{text}///{geom_display}{SHAPE_END_MARKER}"

    elif kind == "diagram":
        name = obj.get("name", "").strip()
        child_parts: List[str] = []
        for child in obj.get("children", []):
            # Recursively format each child (shape, image, nested diagram)
            child_parts.append(_format_drawing_object(child))
        shapes_str = "".join(child_parts)
        return f"{DIAGRAM_START_MARKER}{name}///{shapes_str}{DIAGRAM_END_MARKER}"

    elif kind == "chart":
        return _format_chart_object(obj)

    return ""


# ──────────────────────────────────────────────────────────────────────
# §9  Content extraction helpers
# ──────────────────────────────────────────────────────────────────────

def _format_cell_value_with_link(cd: Dict[str, Any]) -> str:
    """Format a cell value, appending its hyperlink if present."""
    val = cd.get("value", "")
    if val == "" or val is None:
        return ""
    text = str(val).strip()
    link = cd.get("hyperlink", "")
    if link:
        return f"[{text}]({link})"
    return text


def _determine_table_col_range(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    table_row_indices: List[int],
) -> Tuple[int, int]:
    """Return (min_col, max_col) for a table region."""
    all_cols: set[int] = set()
    for r in table_row_indices:
        row = rows.get(r, {})
        for c, cd in row.items():
            val = cd.get("value", "")
            if val != "" and val is not None:
                all_cols.add(c)
    if not all_cols:
        return 0, 0
    return min(all_cols), max(all_cols)


def _cell_to_markdown_text(cd: Dict[str, Any]) -> str:
    """Format a cell value for markdown table output."""
    val = cd.get("value", "")
    if val is None:
        val = ""
    text = str(val).replace("|", "\\|").replace("\n", " ")
    link = cd.get("hyperlink", "")
    if link and text.strip():
        return f"[{text}]({link})"
    return text


def _normalize_header_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def _row_numericish_count_in_range(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
    min_col: int,
    max_col: int,
) -> int:
    """Count cells that look numeric-ish in a row range."""
    count = 0
    for c in range(min_col, max_col + 1):
        cd = rows.get(row_idx, {}).get(c, {})
        text = str(cd.get("value", "") or "").strip()
        if text and re.search(r"\d", text):
            count += 1
    return count


def _has_same_row_merged_copy(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
    min_col: int,
    max_col: int,
) -> bool:
    """Whether the row contains horizontally propagated merged cells."""
    for c in range(min_col, max_col + 1):
        merged_from = rows.get(row_idx, {}).get(c, {}).get("merged_from")
        if not merged_from:
            continue
        try:
            src_row, _ = parse_cell_ref(merged_from)
        except ValueError:
            continue
        if src_row == row_idx:
            return True
    return False


def _has_merge_from_previous_row(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
    min_col: int,
    max_col: int,
) -> bool:
    """Whether the row contains vertically propagated merged cells from above."""
    for c in range(min_col, max_col + 1):
        merged_from = rows.get(row_idx, {}).get(c, {}).get("merged_from")
        if not merged_from:
            continue
        try:
            src_row, _ = parse_cell_ref(merged_from)
        except ValueError:
            continue
        if src_row < row_idx:
            return True
    return False


def _infer_markdown_header_row_count(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    table_row_indices: List[int],
    min_col: int,
    max_col: int,
) -> int:
    """
    Infer how many top rows belong to a visual multi-row header.

    Excel tables like:
      - row 1: ML-1M / Gowalla / Steam / ...
      - row 2: HR / NDCG / HR / NDCG / ...
    should be emitted as one markdown header row by combining the first
    two sheet rows. We detect that from merged-cell propagation:
      - top row has same-row merged copies (horizontal merged groups)
      - second row has values merged down from the first row in some cols
      - the following row looks more data-like than the second row
    """
    if len(table_row_indices) < 3:
        return 1

    first_row = table_row_indices[0]
    second_row = table_row_indices[1]
    third_row = table_row_indices[2]

    if not _has_same_row_merged_copy(rows, first_row, min_col, max_col):
        return 1

    if not _has_merge_from_previous_row(rows, second_row, min_col, max_col):
        return 1

    second_numericish = _row_numericish_count_in_range(rows, second_row, min_col, max_col)
    third_numericish = _row_numericish_count_in_range(rows, third_row, min_col, max_col)
    if third_numericish <= second_numericish:
        return 1

    return 2


def _build_markdown_header_cells(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    header_row_indices: List[int],
    min_col: int,
    max_col: int,
) -> List[str]:
    """Combine one or more sheet header rows into a single markdown header row."""
    header_cells: List[str] = []

    for c in range(min_col, max_col + 1):
        parts: List[str] = []
        last_norm = ""
        for r in header_row_indices:
            text = _cell_to_markdown_text(rows.get(r, {}).get(c, {})).strip()
            if not text:
                continue
            norm = _normalize_header_text(text)
            if norm == last_norm:
                continue
            parts.append(text)
            last_norm = norm

        header_cells.append(" ".join(parts).strip())

    return header_cells


def _grid_to_markdown_table(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    table_row_indices: List[int],
    min_col: int,
    max_col: int,
) -> str:
    """
    Build a Markdown table from explicit row indices.
    Merged-cell values are **duplicated** in every spanned cell.
    Visual multi-row headers are collapsed into one markdown header row.
    """
    if not table_row_indices:
        return ""

    header_row_count = _infer_markdown_header_row_count(
        rows, table_row_indices, min_col, max_col,
    )
    header_row_indices = table_row_indices[:header_row_count]
    data_row_indices = table_row_indices[header_row_count:]

    header_cells = _build_markdown_header_cells(
        rows, header_row_indices, min_col, max_col,
    )

    lines: List[str] = []
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("| " + " | ".join("---" for _ in header_cells) + " |")

    for r in data_row_indices:
        cells: List[str] = []
        for c in range(min_col, max_col + 1):
            cells.append(_cell_to_markdown_text(rows.get(r, {}).get(c, {})))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _row_fill_count(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
) -> int:
    """Count non-empty, non-merged-duplicate cells in a row."""
    row = rows.get(row_idx, {})
    count = 0
    for cd in row.values():
        val = cd.get("value", "")
        if val != "" and val is not None and not cd.get("merged_from"):
            count += 1
    return count


def _row_fill_count_in_col_range(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
    min_col: int,
    max_col: int,
) -> int:
    """
    Count non-empty cells (including merged duplicates) in a row
    within [min_col, max_col].  Merged duplicates are counted because
    they represent visually-filled cells for density detection.
    """
    row = rows.get(row_idx, {})
    count = 0
    for c in range(min_col, max_col + 1):
        cd = row.get(c, {})
        val = cd.get("value", "")
        if val != "" and val is not None:
            count += 1
    return count


def _detect_column_groups(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_indices: List[int],
    min_col: int,
    max_col: int,
) -> List[Tuple[int, int]]:
    """
    Detect groups of adjacent columns that contain data, separated by
    columns that are completely empty across all given rows.

    Returns a list of (start_col, end_col) tuples.  If no empty-column
    gap is found, returns a single group spanning [min_col, max_col].
    """
    col_has_data: Dict[int, bool] = {}
    for c in range(min_col, max_col + 1):
        for r in row_indices:
            cd = rows.get(r, {}).get(c, {})
            val = cd.get("value", "")
            if val != "" and val is not None:
                col_has_data[c] = True
                break

    groups: List[Tuple[int, int]] = []
    in_group = False
    group_start = min_col
    for c in range(min_col, max_col + 1):
        if col_has_data.get(c, False):
            if not in_group:
                group_start = c
                in_group = True
        else:
            if in_group:
                groups.append((group_start, c - 1))
                in_group = False
    if in_group:
        groups.append((group_start, max_col))

    return groups if groups else [(min_col, max_col)]


def _detect_table_ranges_in_columns(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_start: int,
    row_end: int,
    col_start: int,
    col_end: int,
    dense_threshold: int = 2,
    merged_cells: Optional[List[Dict[str, Any]]] = None,
) -> List[Tuple[int, int]]:
    """
    Detect table ranges within a specific column range [col_start, col_end].

    Only cells inside the column range contribute to density.  This ensures
    that side-by-side tables in different column groups are detected
    independently: an empty row in one column group is recognised as a
    table boundary even when the same row has data in another group.

    Uses *gap_tolerance=1* and merges gaps only when the gap row itself
    contains data within the column range.
    """
    # ── Step 1: Find dense rows in column range ──
    dense_rows: set[int] = set()
    for r in range(row_start, row_end + 1):
        fill = _row_fill_count_in_col_range(rows, r, col_start, col_end)
        if fill >= dense_threshold:
            dense_rows.add(r)

    if not dense_rows:
        return []

    # ── Step 2: Build consecutive ranges ──
    sorted_dense = sorted(dense_rows)
    raw_ranges: List[Tuple[int, int]] = []
    start = sorted_dense[0]
    prev = start
    for r in sorted_dense[1:]:
        if r == prev + 1:
            prev = r
        else:
            raw_ranges.append((start, prev))
            start = r
            prev = r
    raw_ranges.append((start, prev))

    # ── Step 3: Merge ranges separated by ≤1 row that has data ──
    GAP_TOLERANCE = 1
    if len(raw_ranges) <= 1:
        merged = list(raw_ranges)
    else:
        merged: List[Tuple[int, int]] = [raw_ranges[0]]
        for sr, er in raw_ranges[1:]:
            prev_sr, prev_er = merged[-1]
            gap = sr - prev_er - 1
            if gap <= GAP_TOLERANCE:
                gap_has_data = any(
                    _row_fill_count_in_col_range(rows, r, col_start, col_end) > 0
                    for r in range(prev_er + 1, sr)
                )
                if gap_has_data:
                    merged[-1] = (prev_sr, er)
                    continue
            merged.append((sr, er))

    # ── Step 4: Extend ranges via merge regions within column bounds ──
    if merged_cells:
        relevant_merges = [
            mc for mc in merged_cells
            if mc["min_col"] >= col_start and mc["max_col"] <= col_end
            and mc["min_row"] != mc["max_row"]
        ]
        changed = True
        iterations = 0
        while changed and iterations < 20:
            changed = False
            iterations += 1
            for i, (sr, er) in enumerate(merged):
                for mc in relevant_merges:
                    mc_sr, mc_er = mc["min_row"], mc["max_row"]
                    if mc_sr <= er and mc_er >= sr:
                        new_sr = min(sr, mc_sr)
                        new_er = max(er, mc_er)
                        if new_sr != sr or new_er != er:
                            merged[i] = (new_sr, new_er)
                            changed = True
            if changed:
                merged.sort()
                deduped: List[Tuple[int, int]] = [merged[0]]
                for sr2, er2 in merged[1:]:
                    prev_sr2, prev_er2 = deduped[-1]
                    if sr2 <= prev_er2 + 1:
                        deduped[-1] = (prev_sr2, max(er2, prev_er2))
                    else:
                        deduped.append((sr2, er2))
                merged = deduped

    return merged


def _is_section_separator(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    row_idx: int,
    min_span: int = 3,
) -> bool:
    """
    Detect section-separator rows: a single value merged across many columns.

    Criteria:
      - Exactly 1 unique non-empty value in the row
      - Only 1 "original" (non-merged) cell (the rest are merged copies)
      - Total filled cells ≥ min_span
    """
    row = rows.get(row_idx, {})
    if not row:
        return False

    unique_values: set[str] = set()
    total_filled = 0
    original_count = 0

    for cd in row.values():
        val = cd.get("value", "")
        if val != "" and val is not None:
            unique_values.add(str(val).strip())
            total_filled += 1
            if not cd.get("merged_from"):
                original_count += 1

    return (
        len(unique_values) == 1
        and original_count == 1
        and total_filled >= min_span
    )


# ──────────────────────────────────────────────────────────────────────
# §10  Semantic table detection ("No Create Table")
#
# Heuristic: consecutive rows where each row has ≥ dense_threshold
# non-empty cells.  The first row of such a block is assumed to be
# the header.  Groups separated by empty rows are distinct tables.
# ──────────────────────────────────────────────────────────────────────

def _detect_table_ranges(
    rows: Dict[int, Dict[int, Dict[str, Any]]],
    max_row: int,
    dense_threshold: int = 3,
    gap_tolerance: int = 2,
    merged_cells: Optional[List[Dict[str, Any]]] = None,
) -> List[Tuple[int, int]]:
    """
    Return list of (start_row, end_row) ranges that look like tables.
    Rows with ≥ *dense_threshold* non-empty cells are "dense".
    Consecutive dense rows form a table region.

    *gap_tolerance*: allow up to N non-dense rows between dense rows
    and still merge them into one table.  This prevents header rows
    (which may have fewer fills due to merged cells) from being split
    away from the data rows.

    *merged_cells*: list of merge-region dicts from ``parse_sheet``.
    Used to extend table ranges to cover continuation rows within
    vertically-merged regions (e.g. PH1003 spanning rows 12-18).

    After extension, ranges are split at section-separator rows
    (single value merged across many columns, e.g. 'LÝ LUẬN CHÍNH TRỊ')
    only when both resulting sub-ranges are large enough (≥ 3 rows).
    """
    dense_rows: set[int] = set()
    for r in range(max_row + 1):
        if _row_fill_count(rows, r) >= dense_threshold:
            dense_rows.add(r)

    if not dense_rows:
        return []

    # ── Step 1: Build initial consecutive-dense ranges ──
    raw_ranges: List[Tuple[int, int]] = []
    sorted_dense = sorted(dense_rows)
    start = sorted_dense[0]
    prev = start
    for r in sorted_dense[1:]:
        if r == prev + 1:
            prev = r
        else:
            raw_ranges.append((start, prev))
            start = r
            prev = r
    raw_ranges.append((start, prev))

    # ── Step 2: Merge ranges separated by small gaps ──
    if len(raw_ranges) <= 1:
        gap_merged = list(raw_ranges)
    else:
        gap_merged: List[Tuple[int, int]] = [raw_ranges[0]]
        for sr, er in raw_ranges[1:]:
            prev_sr, prev_er = gap_merged[-1]
            gap = sr - prev_er - 1
            if gap <= gap_tolerance:
                gap_has_data = any(
                    _row_fill_count(rows, r) > 0 for r in range(prev_er + 1, sr)
                )
                if gap <= 1 or gap_has_data:
                    gap_merged[-1] = (prev_sr, er)
                    continue
            gap_merged.append((sr, er))

    # ── Step 3: Extend ranges via merge regions ──
    # If a merge region overlaps with a table range, extend the range
    # to cover all rows of that merge.  This includes continuation rows
    # that have few unique cells but are part of a vertically-merged block.
    if merged_cells:
        changed = True
        iterations = 0
        while changed and iterations < 20:
            changed = False
            iterations += 1
            for i, (sr, er) in enumerate(gap_merged):
                for mc in merged_cells:
                    mc_sr = mc["min_row"]
                    mc_er = mc["max_row"]
                    if mc_sr == mc_er:
                        continue  # single-row merge, skip
                    # Check overlap: merge region touches the range
                    if mc_sr <= er and mc_er >= sr:
                        new_sr = min(sr, mc_sr)
                        new_er = max(er, mc_er)
                        if new_sr != sr or new_er != er:
                            gap_merged[i] = (new_sr, new_er)
                            changed = True
            # After extension, merge overlapping/adjacent ranges
            if changed:
                gap_merged.sort()
                deduped: List[Tuple[int, int]] = [gap_merged[0]]
                for sr2, er2 in gap_merged[1:]:
                    prev_sr2, prev_er2 = deduped[-1]
                    if sr2 <= prev_er2 + 1:
                        deduped[-1] = (prev_sr2, max(er2, prev_er2))
                    else:
                        deduped.append((sr2, er2))
                gap_merged = deduped

    # ── Step 4: Split at section-separator rows ──
    # A section separator (single merged value spanning many columns)
    # should break a table into two independent tables, but only
    # when both resulting pieces are large enough (≥ MIN_TABLE_ROWS).
    MIN_TABLE_ROWS = 3
    final_ranges: List[Tuple[int, int]] = []
    for sr, er in gap_merged:
        # Find all separator rows within this range
        separators_in_range = [
            r for r in range(sr, er + 1)
            if _is_section_separator(rows, r)
        ]
        if not separators_in_range:
            final_ranges.append((sr, er))
            continue

        # Try to split at each separator (process from first to last)
        current_start = sr
        range_pieces: List[Tuple[int, int]] = []
        for sep_row in separators_in_range:
            before_end = sep_row - 1
            after_start = sep_row + 1
            before_size = before_end - current_start + 1 if before_end >= current_start else 0
            after_size = er - after_start + 1 if after_start <= er else 0

            if before_size >= MIN_TABLE_ROWS and after_size >= MIN_TABLE_ROWS:
                # Valid split
                range_pieces.append((current_start, before_end))
                current_start = after_start
            # else: don't split here, keep the separator in the range

        range_pieces.append((current_start, er))
        final_ranges.extend(range_pieces)

    return final_ranges


# ──────────────────────────────────────────────────────────────────────
# §11  Build linear output per sheet
#
# Parse left-to-right, top-to-bottom.  Interleave cell text, tables,
# and drawing objects (shapes / images / diagrams) by row position.
#
# Output schema (per workbook):
#   [
#     { "sheet_name": "Sheet1",
#       "content": "cell text\n\n[START_TABLE] md [END_TABLE]\n\n[START_SHAPE]…"
#     },
#     ...
#   ]
# ──────────────────────────────────────────────────────────────────────


def _normalize_drawing_anchor_positions(objects: List[Dict[str, Any]]) -> None:
    """
    Cluster drawing objects into visual rows (by y-center, same tolerance
    as ``_order_drawing_objects_reading_order``) and normalise the ``row``
    and ``col`` attributes so that all objects in the same visual row
    share the minimum anchor row and receive ascending virtual column
    indices.  This prevents the final content sort (by anchor row/col)
    from breaking the visual left-to-right order established earlier.

    Mutates *objects* in place.  Assumes they are already in correct
    visual reading order (as returned by ``parse_drawing``).
    """
    if not objects:
        return

    # Build geometry features
    items: List[Tuple[Dict[str, Any], float]] = []  # (obj, y_center)
    heights: List[int] = []
    for o in objects:
        cy = int(o.get("cy", 0) or 0)
        y  = int(o.get("y", 0) or 0)
        h  = cy if cy > 0 else 1
        y_center = y + h / 2.0
        items.append((o, y_center))
        if cy > 0:
            heights.append(cy)

    # Dynamic tolerance (25 % of median height)
    heights.sort()
    if heights:
        mid = len(heights) // 2
        median_h = (
            heights[mid]
            if len(heights) % 2 == 1
            else (heights[mid - 1] + heights[mid]) / 2.0
        )
    else:
        median_h = 1.0
    tol_y = max(1.0, 0.25 * float(median_h))

    # Cluster into visual rows (preserve existing order)
    clusters: List[List[Tuple[Dict[str, Any], float]]] = []
    current: List[Tuple[Dict[str, Any], float]] = [items[0]]
    for item in items[1:]:
        cur_mean = sum(yc for _, yc in current) / len(current)
        if abs(item[1] - cur_mean) <= tol_y:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)

    # For each cluster, assign the minimum anchor row and sequential cols
    for cluster in clusters:
        min_row = min(o.get("row", 0) for o, _ in cluster)
        for seq, (o, _) in enumerate(cluster):
            o["row"] = min_row
            # Use a large col offset so objects within the same visual
            # row sort after any text/table at the same row, and among
            # themselves in the correct left-to-right order.
            o["col"] = seq


def _build_sheet_content(
    sheet_data: Dict[str, Any],
    parsed_dir: Path,
) -> str:
    """
    Build the flat content string for one sheet by scanning
    top-to-bottom, left-to-right.

    Content items emitted in order:
      1. Free text rows (not part of any table)
      2. Table blocks (structural or semantic)
      3. Drawing objects (shapes, images, diagrams) interleaved by row
    """
    grid_rows: Dict[int, Dict[int, Dict[str, Any]]] = sheet_data.get("rows", {})
    max_row = sheet_data.get("row_count", 0)

    # ── 1. Determine which cells belong to structural tables ──
    # Track consumed cells as (row, col) pairs so that a structural
    # table spanning cols B-E does NOT block data in cols G-J on the
    # same rows (e.g. PERSONAL CARE vs. the summary block).
    structural_cells: set[Tuple[int, int]] = set()
    table_blocks: List[Dict[str, Any]] = []  # {start_row, end_row, md}

    for tbl in sheet_data.get("tables", []):
        ref = tbl.get("ref", "")
        if not ref:
            continue
        try:
            r1, c1, r2, c2 = parse_range_ref(ref)
        except (ValueError, IndexError):
            continue

        # Expand upward: include adjacent dense rows above the table ref
        # that are likely multi-row merged headers (e.g. dataset names
        # spanning columns above the actual HR/NDCG header row).
        # IMPORTANT: only count fills within the table's own column range
        # so that data in neighbouring column groups doesn't cause
        # unbounded upward expansion (e.g. side-by-side budget tables).
        while r1 > 0:
            above = r1 - 1
            fill = _row_fill_count_in_col_range(grid_rows, above, c1, c2)
            if fill >= 2:  # low threshold   merged headers often have few unique cells
                r1 = above
            else:
                break

        tbl_row_list = list(range(r1, r2 + 1))
        for r in tbl_row_list:
            for c in range(c1, c2 + 1):
                structural_cells.add((r, c))
        md = _grid_to_markdown_table(grid_rows, tbl_row_list, c1, c2)
        if md:
            table_blocks.append({
                "start_row": r1,
                "end_row": r2,
                "start_col": c1,
                "md": md,
                "name": tbl.get("display_name", tbl.get("name", "")),
            })

    # ── 2. Semantic table detection on remaining rows ──
    # Build remaining_rows by removing cells already consumed by
    # structural tables.  A row is included if it has any non-consumed
    # cells; consumed cells are replaced with empty entries so density
    # detection ignores them.
    remaining_rows: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for r in range(max_row + 1):
        if r not in grid_rows:
            continue
        filtered_row: Dict[int, Dict[str, Any]] = {}
        for c, cd in grid_rows[r].items():
            if (r, c) not in structural_cells:
                filtered_row[c] = cd
        if filtered_row:
            remaining_rows[r] = filtered_row

    all_merged_cells = sheet_data.get("merged_cells", [])
    sem_ranges = _detect_table_ranges(
        remaining_rows, max_row, dense_threshold=3,
        merged_cells=all_merged_cells,
    )
    for (sr, er) in sem_ranges:
        tbl_row_list = list(range(sr, er + 1))
        min_c, max_c = _determine_table_col_range(grid_rows, tbl_row_list)

        # Detect column groups (side-by-side tables separated by
        # empty columns).  When multiple groups exist, split
        # horizontally first, then re-detect vertical boundaries
        # within each group using column-scoped fill counts.
        col_groups = _detect_column_groups(
            grid_rows, tbl_row_list, min_c, max_c,
        )

        if len(col_groups) > 1:
            for cg_start, cg_end in col_groups:
                sub_ranges = _detect_table_ranges_in_columns(
                    grid_rows, sr, er, cg_start, cg_end,
                    dense_threshold=2,
                    merged_cells=all_merged_cells,
                )
                for sub_sr, sub_er in sub_ranges:
                    if sub_sr == sub_er:
                        continue
                    sub_row_list = list(range(sub_sr, sub_er + 1))
                    md = _grid_to_markdown_table(
                        grid_rows, sub_row_list, cg_start, cg_end,
                    )
                    if md:
                        for r in sub_row_list:
                            for c in range(cg_start, cg_end + 1):
                                structural_cells.add((r, c))
                        table_blocks.append({
                            "start_row": sub_sr,
                            "end_row": sub_er,
                            "start_col": cg_start,
                            "md": md,
                            "name": "",
                        })
        else:
            # Single column group   process as before
            md = _grid_to_markdown_table(
                grid_rows, tbl_row_list, min_c, max_c,
            )
            if md:
                for r in tbl_row_list:
                    for c in range(min_c, max_c + 1):
                        structural_cells.add((r, c))
                table_blocks.append({
                    "start_row": sr,
                    "end_row": er,
                    "start_col": min_c,
                    "md": md,
                    "name": "",
                })

    # Sort table blocks by start row, then by start column
    table_blocks.sort(key=lambda t: (t["start_row"], t.get("start_col", 0)))

    # ── 2b. Residual pass   catch small table-like blocks missed by the
    #    dense_threshold=3 of _detect_table_ranges.  This handles e.g.
    #    summary blocks (TOTAL PROJECTED COST / TOTAL ACTUAL COST) where
    #    merged labels give only 2 non-merged fills per row.
    #
    #    Strategy: rebuild remaining_rows after step 2, cluster the
    #    residual rows into contiguous groups, detect column groups
    #    within each cluster, and run column-aware table detection
    #    using *residual_rows* (not grid_rows) so already-consumed
    #    cells don't inflate density counts.
    residual_rows: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for r in range(max_row + 1):
        if r not in grid_rows:
            continue
        filtered_row: Dict[int, Dict[str, Any]] = {}
        for c, cd in grid_rows[r].items():
            if (r, c) not in structural_cells:
                val = cd.get("value", "")
                if val != "" and val is not None:
                    filtered_row[c] = cd
        if filtered_row:
            residual_rows[r] = filtered_row

    if residual_rows:
        # Cluster residual rows into contiguous groups.  Rows separated
        # by large gaps (> 2 rows) are treated independently so that
        # e.g. row 1 (title) doesn't get grouped with rows 57-62
        # (summary block).
        residual_row_indices = sorted(residual_rows.keys())
        row_clusters: List[List[int]] = []
        current_cluster: List[int] = [residual_row_indices[0]]
        for ri in residual_row_indices[1:]:
            if ri - current_cluster[-1] <= 2:
                current_cluster.append(ri)
            else:
                row_clusters.append(current_cluster)
                current_cluster = [ri]
        row_clusters.append(current_cluster)

        for cluster in row_clusters:
            cluster_min_r, cluster_max_r = cluster[0], cluster[-1]
            all_residual_cols: set[int] = set()
            for r in cluster:
                all_residual_cols.update(residual_rows[r].keys())
            if not all_residual_cols:
                continue
            res_min_c, res_max_c = min(all_residual_cols), max(all_residual_cols)

            # Detect column groups within this cluster using
            # residual_rows so empty-column gaps are correct.
            res_col_groups = _detect_column_groups(
                residual_rows, cluster, res_min_c, res_max_c,
            )
            for cg_start, cg_end in res_col_groups:
                # Use residual_rows for density detection so consumed
                # cells don't make rows appear dense.
                sub_ranges = _detect_table_ranges_in_columns(
                    residual_rows,
                    cluster_min_r, cluster_max_r,
                    cg_start, cg_end,
                    dense_threshold=2,
                    merged_cells=all_merged_cells,
                )
                for sub_sr, sub_er in sub_ranges:
                    # Skip single-row blocks   they are titles /
                    # headings that should remain as free text.
                    if sub_sr == sub_er:
                        continue
                    sub_row_list = list(range(sub_sr, sub_er + 1))
                    md = _grid_to_markdown_table(
                        grid_rows, sub_row_list, cg_start, cg_end,
                    )
                    if md:
                        for r in sub_row_list:
                            for c in range(cg_start, cg_end + 1):
                                structural_cells.add((r, c))
                        table_blocks.append({
                            "start_row": sub_sr,
                            "end_row": sub_er,
                            "start_col": cg_start,
                            "md": md,
                            "name": "",
                        })

        # Re-sort after residual additions
        table_blocks.sort(key=lambda t: (t["start_row"], t.get("start_col", 0)))

    # ── 3. Parse drawing objects ──
    drawing_objects: List[Dict[str, Any]] = []
    for drawing_target in sheet_data.get("drawings", []):
        # drawing_target is a relative path like "../drawings/drawing1.xml"
        if not drawing_target:
            continue
        # Resolve relative to xl/worksheets/
        drawing_xml = (parsed_dir / "xl" / "worksheets" / drawing_target).resolve()
        if not drawing_xml.exists():
            drawing_xml = (parsed_dir / "xl" / drawing_target.lstrip("/")).resolve()
        if not drawing_xml.exists():
            # Manually resolve "../" segments
            parts = drawing_target.replace("\\", "/").split("/")
            drawing_xml = parsed_dir / "xl" / "worksheets"
            for p in parts:
                if p == "..":
                    drawing_xml = drawing_xml.parent
                else:
                    drawing_xml = drawing_xml / p
            drawing_xml = drawing_xml.resolve()
        if drawing_xml.exists():
            objs = parse_drawing(drawing_xml, parsed_dir)
            drawing_objects.extend(objs)

    # ── 3b. Normalize anchor rows for visually same-row drawing objects ──
    # parse_drawing returns objects in correct visual reading order
    # (top-to-bottom, left-to-right via y-center clustering).  However,
    # step 5 re-sorts by (anchor_row, priority, anchor_col), which can
    # break the visual order when objects share a visual row but have
    # different cell-anchor rows (e.g. images at row 76 and row 78 that
    # are visually side-by-side).  Fix: cluster by y-center (same logic
    # as _order_drawing_objects_reading_order) and assign each cluster
    # the minimum anchor row, plus sequential columns to preserve order.
    if len(drawing_objects) > 1:
        _normalize_drawing_anchor_positions(drawing_objects)

    # ── 4. Build unified content items list ──
    # Each item: (row_position, priority, col_position, content_string)
    #   priority: 0 = text row, 1 = table block, 2 = drawing object
    #   Lower priority number means it appears first when at same row.
    #   col_position breaks ties for side-by-side tables (left before right).
    content_items: List[Tuple[int, int, int, str]] = []

    # 4a. Free text rows   emit only cells not consumed by any table
    for r in range(max_row + 1):
        row = grid_rows.get(r, {})
        if not row:
            continue
        # Check if every filled cell in this row is consumed
        has_unconsumed = False
        for c, cd in row.items():
            if (r, c) not in structural_cells:
                val = cd.get("value", "")
                if val != "" and val is not None and not cd.get("merged_from"):
                    has_unconsumed = True
                    break
        if not has_unconsumed:
            continue
        # Build text only from unconsumed cells
        parts: List[str] = []
        for c in sorted(row.keys()):
            if (r, c) in structural_cells:
                continue
            cd = row[c]
            val = cd.get("value", "")
            if val == "" or val is None:
                continue
            if cd.get("merged_from"):
                continue
            parts.append(_format_cell_value_with_link(cd))
        txt = "\t".join(parts)
        if txt:
            content_items.append((r, 0, 0, txt))

    # 4b. Table blocks
    for tbl in table_blocks:
        md_content = f"{TABLE_START_MARKER}\n{tbl['md']}\n{TABLE_END_MARKER}"
        content_items.append((tbl["start_row"], 1, tbl.get("start_col", 0), md_content))

    # 4c. Drawing objects (positioned by their cell anchor row)
    for obj in drawing_objects:
        formatted = _format_drawing_object(obj)
        if formatted:
            obj_row = obj.get("row", max_row + 1)
            content_items.append((obj_row, 2, obj.get("col", 0), formatted))

    # ── 5. Sort by row, then priority, then column and join ──
    content_items.sort(key=lambda item: (item[0], item[1], item[2]))

    content_strings = [item[3] for item in content_items]
    return "\n".join(content_strings)


def _parse_chartsheet_linear(
    parsed_dir: Path,
    sheet_meta: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Parse a chartsheet → {"sheet_name": str, "content": str} or None.

    Chartsheets have no cell data   they contain only a drawing reference
    which embeds a chart.  We resolve:
      chartsheet XML → <drawing r:id="…"/> → drawingN.xml → graphicFrame → chartN.xml
    """
    sheet_name = sheet_meta["name"]
    xml_rel_path = sheet_meta.get("xml_path", "")
    if not xml_rel_path:
        log.warning("No XML path for chartsheet '%s'   skipping", sheet_name)
        return None

    cs_xml = parsed_dir / "xl" / xml_rel_path
    if not cs_xml.exists():
        log.warning("Chartsheet XML not found: %s", cs_xml)
        return None

    log.info("Parsing chartsheet '%s' from %s", sheet_name, cs_xml.name)

    # Parse the chartsheet XML to find its drawing reference
    tree = ET.parse(cs_xml)
    root = tree.getroot()

    # Load chartsheet rels to resolve drawing rId
    cs_rels_path = cs_xml.parent / "_rels" / f"{cs_xml.name}.rels"
    cs_rels = _parse_rels(cs_rels_path)

    drawing_target = ""
    draw_el = root.find(f"{{{NS_SPREADSHEET}}}drawing")
    if draw_el is not None:
        draw_rid = draw_el.get(f"{{{NS_REL}}}id", "")
        if draw_rid and draw_rid in cs_rels:
            drawing_target = cs_rels[draw_rid]["target"]

    if not drawing_target:
        log.warning("No drawing found in chartsheet '%s'", sheet_name)
        return None

    # Resolve drawing path relative to the chartsheet's directory
    drawing_xml = (cs_xml.parent / drawing_target).resolve()
    if not drawing_xml.exists():
        drawing_xml = (parsed_dir / "xl" / drawing_target.lstrip("/")).resolve()
    if not drawing_xml.exists():
        log.warning("Drawing XML not found for chartsheet '%s': %s", sheet_name, drawing_target)
        return None

    # Parse the drawing   will now pick up graphicFrame → chart objects
    drawing_objects = parse_drawing(drawing_xml, parsed_dir)

    content_parts: List[str] = []
    for obj in drawing_objects:
        formatted = _format_drawing_object(obj)
        if formatted:
            content_parts.append(formatted)

    return {
        "sheet_name": sheet_name,
        "content": "\n".join(content_parts),
    }


def _parse_sheet_linear(
    parsed_dir: Path,
    sheet_meta: Dict[str, Any],
    shared_values: List[str],
    styles: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Parse one worksheet → {"sheet_name": str, "content": str} or None."""
    sheet_name = sheet_meta["name"]
    xml_rel_path = sheet_meta.get("xml_path", "")
    if not xml_rel_path:
        log.warning("No XML path for sheet '%s'   skipping", sheet_name)
        return None

    sheet_xml = parsed_dir / "xl" / xml_rel_path
    resolved = sheet_xml.with_name(f"{sheet_xml.stem}.resolved{sheet_xml.suffix}")
    actual_path = resolved if resolved.exists() else sheet_xml

    if not actual_path.exists():
        log.warning("Sheet XML not found: %s", actual_path)
        return None

    sheet_rels_path = sheet_xml.parent / "_rels" / f"{sheet_xml.name}.rels"

    log.info("Parsing sheet '%s' from %s", sheet_name, actual_path.name)
    sheet_data = parse_sheet(
        actual_path,
        shared_values,
        sheet_rels_path=sheet_rels_path if sheet_rels_path.exists() else None,
        styles=styles,
        parsed_dir=parsed_dir,
    )

    content = _build_sheet_content(sheet_data, parsed_dir)

    return {
        "sheet_name": sheet_name,
        "content": content,
    }


def build_workbook_output(
    parsed_dir: Path,
    shared_values: List[str],
    source_filename: str = "",
) -> List[Dict[str, Any]]:
    """
    Build the linear output for the entire workbook.

    Returns a list of dicts (one per sheet):
        {"sheet_name": str, "content": str}
    """
    wb_meta = parse_workbook(parsed_dir)
    styles = parse_styles(parsed_dir)
    result: List[Dict[str, Any]] = []

    for sheet_meta in wb_meta.get("sheets", []):
        sheet_type = sheet_meta.get("sheet_type", "worksheet")
        if sheet_type == "chartsheet":
            sheet_result = _parse_chartsheet_linear(parsed_dir, sheet_meta)
        else:
            sheet_result = _parse_sheet_linear(
                parsed_dir, sheet_meta, shared_values, styles,
            )
        if sheet_result is not None:
            result.append(sheet_result)

    return result


# ──────────────────────────────────────────────────────────────────────
# §12  Process a single Excel file end-to-end
# ──────────────────────────────────────────────────────────────────────

def _detect_and_convert_xls(path: Path, temp_dir: Path) -> Path:
    """Convert legacy .xls or .xlsm to .xlsx using LibreOffice.

    Returns the path to the converted .xlsx file inside *temp_dir*.
    The caller is responsible for cleaning up *temp_dir*.
    """
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "xlsx",
         "--outdir", str(temp_dir), str(path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice .xls/.xlsm→.xlsx conversion failed: {result.stderr}")
    converted = temp_dir / (path.stem + ".xlsx")
    if not converted.exists():
        raise FileNotFoundError(f"Converted file not found: {converted}")
    return converted


def process_excel_file(
    excel_path: Path,
    output_dir: Path = OUTPUT_DIR,
    parsed_parent: Path = PARSED_DIR,
) -> Path:
    """
    Full pipeline: unzip → resolve shared strings → parse → write JSON.
    Returns the output JSON path.

    Supports legacy .xls and .xlsm files by converting them to .xlsx via
    LibreOffice before processing.
    """
    excel_path = Path(excel_path)
    temp_dir_obj = None

    # Legacy .xls / .xlsm → convert to .xlsx first
    if excel_path.suffix.lower() in (".xls", ".xlsm"):
        temp_dir_obj = Path(tempfile.mkdtemp(prefix="xls2xlsx_"))
        try:
            converted = _detect_and_convert_xls(excel_path, temp_dir_obj)
            original_stem = excel_path.stem
            excel_path = converted
        except Exception:
            shutil.rmtree(temp_dir_obj, ignore_errors=True)
            raise
    else:
        original_stem = excel_path.stem

    try:
        log.info("=" * 70)
        log.info("Processing: %s", excel_path.name)
        log.info("=" * 70)

        # Step 1: Unzip
        parsed_dir = unzip_excel(excel_path, parsed_parent)

        # Step 2: Resolve shared strings
        shared_values = resolve_shared_strings(parsed_dir)

        # Step 3: Build linear output
        result = build_workbook_output(
            parsed_dir, shared_values, source_filename=excel_path.name
        )

        # Step 4: Write JSON (use original stem so output name matches input)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (original_stem + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        log.info("Output written to: %s", out_path)
        return out_path
    finally:
        if temp_dir_obj is not None:
            shutil.rmtree(temp_dir_obj, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────
# §13  Process from already-parsed directory (no raw file needed)
# ──────────────────────────────────────────────────────────────────────

def process_parsed_dir(
    parsed_dir: Path,
    output_dir: Path = OUTPUT_DIR,
    source_filename: str = "",
) -> Path:
    """
    Process an already-unzipped Excel directory.
    Useful for the parsed/excel/<name>/ folders that already exist.
    """
    log.info("=" * 70)
    log.info("Processing parsed dir: %s", parsed_dir.name)
    log.info("=" * 70)

    shared_values = resolve_shared_strings(parsed_dir)

    result = build_workbook_output(
        parsed_dir, shared_values,
        source_filename=source_filename or parsed_dir.name,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    name = (source_filename.rsplit(".", 1)[0] if source_filename else parsed_dir.name)
    out_path = output_dir / (name + ".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    log.info("Output written to: %s", out_path)
    return out_path


# ──────────────────────────────────────────────────────────────────────
# §14  CLI entry point
# ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Excel files from XML structure into structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python xlsx_reader_v2.py                          # process all raw/*.xlsx files
  python xlsx_reader_v2.py --file raw/excel/Book1.xlsx
  python xlsx_reader_v2.py --parsed-dir parsed/excel/courseware
  python xlsx_reader_v2.py --all-parsed             # process all parsed dirs
        """,
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Path to a single raw Excel file (.xlsx/.xlsm) to process",
    )
    parser.add_argument(
        "--parsed-dir", type=str, default=None,
        help="Path to an already-unzipped parsed directory to process",
    )
    parser.add_argument(
        "--all-parsed", action="store_true",
        help="Process all existing directories in parsed/excel/",
    )
    parser.add_argument(
        "--raw-dir", type=str, default=str(RAW_DIR),
        help=f"Directory containing raw Excel files (default: {RAW_DIR})",
    )
    parser.add_argument(
        "--output-dir", type=str, default=str(OUTPUT_DIR),
        help=f"Output directory for JSON files (default: {OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    results: List[Path] = []

    if args.file:
        fpath = Path(args.file)
        if not fpath.exists():
            log.error("File not found: %s", fpath)
            return 1
        out = process_excel_file(fpath, output_dir)
        results.append(out)

    elif args.parsed_dir:
        pdir = Path(args.parsed_dir)
        if not pdir.exists():
            log.error("Parsed directory not found: %s", pdir)
            return 1
        out = process_parsed_dir(pdir, output_dir)
        results.append(out)

    elif args.all_parsed:
        parsed_parent = PARSED_DIR
        if not parsed_parent.exists():
            log.error("Parsed parent not found: %s", parsed_parent)
            return 1
        for d in sorted(parsed_parent.iterdir()):
            if d.is_dir() and (d / "xl" / "workbook.xml").exists():
                try:
                    out = process_parsed_dir(d, output_dir)
                    results.append(out)
                except Exception:
                    log.exception("Failed to process parsed dir: %s", d.name)

    else:
        raw_dir = Path(args.raw_dir)
        if not raw_dir.exists():
            log.error("Raw directory not found: %s", raw_dir)
            return 1
        excel_files = sorted(
            f for f in raw_dir.iterdir()
            if f.suffix.lower() in (".xlsx", ".xlsm")
            and not f.name.startswith("~")
            and not f.name.startswith(".")
        )
        if not excel_files:
            log.warning("No Excel files found in %s", raw_dir)
            return 0

        log.info("Found %d Excel file(s) to process", len(excel_files))
        for fpath in excel_files:
            try:
                out = process_excel_file(fpath, output_dir)
                results.append(out)
            except Exception:
                log.exception("Failed to process: %s", fpath.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
