"""
This module provides tools to parse Microsoft Word (.docx) files by directly
reading the underlying XML structure.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import numpy as np
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from lxml import etree
from dataclasses import dataclass
from itertools import chain, islice
from copy import deepcopy
from PIL import Image

# Namespaces
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
WPG_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
V_NS = "urn:schemas-microsoft-com:vml"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"

NSMAP = {
    "w": W_NS,
    "a": A_NS,
    "wp": WP_NS,
    "wps": WPS_NS,
    "pic": PIC_NS,
    "r": R_NS,
    "v": V_NS,
    "mc": MC_NS,
}

# Package/content/relationship namespace URIs
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PKG_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

SHAPE_CONTENT_START_MARKER = "[START_SHAPE_CONTENT]"
SHAPE_CONTENT_END_MARKER = "[END_SHAPE_CONTENT]"
IMG_PATH_START_MARKER = "[START_IMAGE_PATH]"
IMG_PATH_END_MARKER = "[END_IMAGE_PATH]"

LVL_TEXT_PATTERN = re.compile(r"%(\d+)")
log = logging.getLogger(__name__)

HEX6_UPPER_RE = r"[0-9A-F]{6}"
HEX6_RE = r"[0-9A-Fa-f]{6}"
# Common DOCX part paths and content type names
DOCX_DOC_XML = "word/document.xml"
DOCX_NUMBERING_XML = "word/numbering.xml"
DOCX_STYLES_XML = "word/styles.xml"
DOCX_SETTINGS_XML = "word/settings.xml"
DOCX_THEME1_XML = "word/theme/theme1.xml"
DOCX_FONT_TABLE_XML = "word/fontTable.xml"
DOCX_RELS_DOCUMENT = "word/_rels/document.xml.rels"
CONTENT_TYPES_XML = "[Content_Types].xml"
WORD_PREFIX = "word/"
WORD_PREFIX_SLASH = "/word/"

def create_ns(namespace: str, tag: str) -> str:
    """Helper to create namespaced XML tags."""
    return f"{{{namespace}}}{tag}"


def _elem_has_any_child(elem, ns: str, *tags: str) -> bool:
    """Return True if elem is not None and contains a child matching any of tags in ns."""
    if elem is None:
        return False
    return any(elem.find(create_ns(ns, t)) is not None for t in tags)


@dataclass
class FillSpec(object):
    """A normalized shading specification found in w:shd."""
    # explicit RGB like "A6A6A6"
    fill_hex: str = ""
    # e.g. "background1", "accent1"
    theme_fill: str = ""
    # 2-hex like "A6"
    theme_shade: str = ""
    # 2-hex like "40"
    theme_tint: str = ""
    # debug: where this spec came from (tc/tr/style)
    source: str = ""


class _VmergeState(object):
    """Tracks active vertical-merge regions across table rows.

    Each attribute is a parallel list indexed by column number (0 … C-1).

    Attributes
    ----------
    on : list[bool]
        True when the column is part of an active vertical merge region.
    text : list[str]
        The text value propagated downward through the merge region.
    mask : list[bool]
        True when the merge region should be blanked (gray / deleted).
    started_here : list[bool]
        Per-row flag: True when a vertical merge was started in this
        column during the current row.  Reset by ``begin_row()``.
    """

    _slots_ = ("on", "text", "mask", "started_here")

    def __init__(self, col_count: int) -> None:
        self.on: list = [False] * col_count
        self.text: list = [""] * col_count
        self.mask: list = [False] * col_count
        self.started_here: list = [False] * col_count

    def begin_row(self) -> None:
        """Reset per-row tracking before processing a new table row."""
        for i in range(len(self.started_here)):
            self.started_here[i] = False

class ThemeResolver(object):
    """
    Resolve theme scheme colors from word/theme/theme1.xml.
    Supports mapping Word themeFill keys to clrScheme keys.
    Applies themeFillShade/themeFillTint by simple linear darken/lighten.
    """

    WORD_TO_SCHEME = {
        # WordprocessingML themeFill values -> theme clrScheme entries
        "text1": "dk1",
        "background1": "lt1",
        "text2": "dk2",
        "background2": "lt2",
        "accent1": "accent1",
        "accent2": "accent2",
        "accent3": "accent3",
        "accent4": "accent4",
        "accent5": "accent5",
        "accent6": "accent6",
        "hyperlink": "hlink",
        "followedHyperlink": "folHlink",
        "hlink": "hlink",
        "folHlink": "folHlink",
        "dk1": "dk1",
        "lt1": "lt1",
        "dk2": "dk2",
        "lt2": "lt2",
    }

    def __init__(self, theme1_xml: Optional[bytes]):
        self.scheme_rgb: Dict[str, str] = {}
        if theme1_xml:
            self._build(theme1_xml)

    def _build(self, theme1_xml: bytes) -> None:
        try:
            root = etree.fromstring(theme1_xml)
        except Exception:
            return

        # Find a:clrScheme inside a:themeElements
        clr_scheme = root.find(f".//{{{A_NS}}}themeElements/{{{A_NS}}}clrScheme")
        if clr_scheme is None:
            return

        # Each entry is like <a:dk1><a:sysClr lastClr="000000"/></a:dk1>
        for child in clr_scheme:
            # dk1, lt1, accent1...
            key = etree.QName(child).localname
            # sysClr lastClr or srgbClr val
            sysclr = child.find(f".//{{{A_NS}}}sysClr")
            srgb = child.find(f".//{{{A_NS}}}srgbClr")
            hexval = ""
            if sysclr is not None:
                hexval = sysclr.get("lastClr", "") or ""
            if not hexval and srgb is not None:
                hexval = srgb.get("val", "") or ""
            hexval = hexval.strip().upper()
            if re.fullmatch(HEX6_UPPER_RE, hexval):
                self.scheme_rgb[key] = hexval

    @staticmethod
    def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
        h = h.upper()
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @staticmethod
    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        return f"{max(0,min(255,r)):02X}{max(0,min(255,g)):02X}{max(0,min(255,b)):02X}"

    @staticmethod
    def _apply_shade(rgb: Tuple[int,int,int], shade_byte: int) -> Tuple[int,int,int]:
        """
        Apply a shade factor (0..255) as a darkening multiplier.
        This is a best-effort model. It works well for typical template shades.
        """
        r,g,b = rgb
        t = max(0, min(255, shade_byte)) / 255.0
        # darker when t is high-ish
        return (int(r * (1.0 - 0.5*t)), int(g * (1.0 - 0.5*t)), int(b * (1.0 - 0.5*t)))

    @staticmethod
    def _apply_tint(rgb: Tuple[int,int,int], tint_byte: int) -> Tuple[int,int,int]:
        """
        Apply a tint factor (0..255) as a lightening interpolation toward white.
        """
        r,g,b = rgb
        t = max(0, min(255, tint_byte)) / 255.0
        return (int(r + (255 - r)*t), int(g + (255 - g)*t), int(b + (255 - b)*t))

    def resolve_to_hex(self, spec: FillSpec) -> str:
        """
        Convert FillSpec to an RGB hex string if possible.
        Priority:
          - explicit fill_hex if present
          - else theme_fill -> scheme rgb
          - then apply shade/tint
        """
        if spec.fill_hex and re.fullmatch(HEX6_RE, spec.fill_hex):
            return spec.fill_hex.upper()

        base = self._resolve_theme_base_color(spec)
        if not base:
            return ""

        rgb = self._hex_to_rgb(base)

        if spec.theme_shade and re.fullmatch(r"[0-9A-Fa-f]{2}", spec.theme_shade):
            rgb = self._apply_shade(rgb, int(spec.theme_shade, 16))
        if spec.theme_tint and re.fullmatch(r"[0-9A-Fa-f]{2}", spec.theme_tint):
            rgb = self._apply_tint(rgb, int(spec.theme_tint, 16))

        return self._rgb_to_hex(*rgb)

    def _resolve_theme_base_color(self, spec: FillSpec) -> str:
        """Resolve the base RGB hex from theme fill specification."""
        if not spec.theme_fill:
            return ""
        word_key = spec.theme_fill.strip()
        scheme_key = self.WORD_TO_SCHEME.get(word_key, "")
        return self.scheme_rgb.get(scheme_key, "")

class TableStyleHelper(object):
    """
    Resolve table cell shading from styles.xml (correct scoping).
    Only reads shading from:
      - default style shading:   w:style / w:tcPr / w:shd
      - conditional shading:     w:style / w:tblStylePr[@type] / w:tcPr / w:shd
    NEVER uses ".//w:shd" fallback (it causes conditional shading to leak into default).
    """

    CNF_TO_TYPES = [
        ("firstRowFirstColumn", "nwCell"),
        ("firstRowLastColumn", "neCell"),
        ("lastRowFirstColumn", "swCell"),
        ("lastRowLastColumn", "seCell"),
        ("firstRow", "firstRow"),
        ("lastRow", "lastRow"),
        ("firstColumn", "firstCol"),
        ("lastColumn", "lastCol"),
        ("oddHBand", "band1Horz"),
        ("evenHBand", "band2Horz"),
        ("oddVBand", "band1Vert"),
        ("evenVBand", "band2Vert"),
    ]

    def __init__(self, styles_xml: Optional[bytes]):
        self.default_spec: Dict[str, FillSpec] = {}
        self.conditional_spec: Dict[str, Dict[str, FillSpec]] = {}
        if styles_xml:
            self._build(styles_xml)

    @staticmethod
    def _parse_shd(shd_el, source: str) -> FillSpec:
        if shd_el is None:
            return FillSpec()

        fill = (shd_el.get(create_ns(W_NS, "fill")) or shd_el.get("fill") or "").strip().upper()
        theme_fill = (shd_el.get(create_ns(W_NS, "themeFill")) or shd_el.get("themeFill") or "").strip()
        theme_shade = (shd_el.get(create_ns(W_NS, "themeFillShade")) or shd_el.get("themeFillShade") or "").strip()
        theme_tint = (shd_el.get(create_ns(W_NS, "themeFillTint")) or shd_el.get("themeFillTint") or "").strip()

        if fill and not re.fullmatch(HEX6_UPPER_RE, fill):
            fill = ""

        return FillSpec(
            fill_hex=fill,
            theme_fill=theme_fill,
            theme_shade=theme_shade,
            theme_tint=theme_tint,
            source=source
        )

    def _build(self, styles_xml: bytes) -> None:
        try:
            root = etree.fromstring(styles_xml)
        except Exception:
            return

        for style in root.findall(create_ns(W_NS, "style")):
            self._process_single_table_style(style)

    def _process_single_table_style(self, style) -> None:
        """Process a single style element for table shading information."""
        if style.get(create_ns(W_NS, "type")) != "table":
            return

        style_id = style.get(create_ns(W_NS, "styleId"))
        if not style_id:
            return

        # DEFAULT shading: ONLY direct child <w:tcPr><w:shd/>
        shd_default = style.find(f"./{create_ns(W_NS,'tcPr')}/{create_ns(W_NS,'shd')}")
        spec_default = self._parse_shd(shd_default, source=f"style:{style_id}:default")
        if spec_default.fill_hex or spec_default.theme_fill:
            self.default_spec[style_id] = spec_default

        # CONDITIONAL shading: tblStylePr[@type] / tcPr / shd
        cond_map = self._extract_conditional_shading(style, style_id)
        if cond_map:
            self.conditional_spec[style_id] = cond_map

    def _extract_conditional_shading(self, style, style_id: str) -> Dict[str, FillSpec]:
        """Extract conditional shading specs from tblStylePr elements."""
        cond_map: Dict[str, FillSpec] = {}
        for tsp in style.findall(create_ns(W_NS, "tblStylePr")):
            tname = tsp.get(create_ns(W_NS, "type"))
            if not tname:
                continue
            shd_cond = tsp.find(f"./{create_ns(W_NS,'tcPr')}/{create_ns(W_NS,'shd')}")
            spec_cond = self._parse_shd(shd_cond, source=f"style:{style_id}:{tname}")
            if spec_cond.fill_hex or spec_cond.theme_fill:
                cond_map[tname] = spec_cond
        return cond_map

    def resolve_spec(self, style_id: str, cnf_attrs: Dict[str, str]) -> FillSpec:
        if not style_id:
            return FillSpec()

        cond = self.conditional_spec.get(style_id, {})

        # match most specific first
        for cnf_key, tname in self.CNF_TO_TYPES:
            if cnf_attrs.get(cnf_key) in {"1", "true", "on"} and tname in cond:
                return cond[tname]

        return self.default_spec.get(style_id, FillSpec())

class NumberingHelper(object):
    """Resolve Word numbering definitions so list/heading markers are emitted as text."""

    def __init__(self, numbering_xml: Optional[bytes]):
        self.levels: Dict[str, Dict[int, Dict[str, Union[str, int, None]]]] = {}
        # numId -> abstractNumId
        self.num_to_abstract: Dict[str, Optional[str]] = {}
        # counters[numId][ilvl] = current int
        self.counters: Dict[str, Dict[int, int]] = defaultdict(dict)
        # shared counters per abstractNumId (helps when Word reuses abstractNum with different numIds)
        self.abstract_counters: Dict[str, Dict[int, int]] = defaultdict(dict)
        if numbering_xml:
            self._build(numbering_xml)

    def _build(self, numbering_xml: bytes) -> None:
        try:
            root = etree.fromstring(numbering_xml)
        except Exception as e:
            log.warning(f"Failed to parse numbering.xml: {e}")
            return

        # 1) Parse abstractNum definitions
        abstract_levels = self._parse_all_abstract_nums(root)

        # 2) Parse num instances + apply overrides
        for num in root.findall(create_ns(W_NS, 'num')):
            self._parse_single_num_instance(num, abstract_levels)

    def _parse_all_abstract_nums(self, root) -> Dict[str, Dict[int, Dict[str, Union[str, int, None]]]]:
        """Parse all abstractNum elements into level definitions."""
        abstract_levels: Dict[str, Dict[int, Dict[str, Union[str, int, None]]]] = {}
        for abstract in root.findall(create_ns(W_NS, 'abstractNum')):
            abstract_id = abstract.get(create_ns(W_NS, 'abstractNumId'))
            if not abstract_id:
                continue
            abstract_levels[abstract_id] = self._parse_abstract_levels(abstract)
        return abstract_levels

    def _parse_single_num_instance(self, num, abstract_levels) -> None:
        """Parse a single num element and apply level overrides."""
        num_id = num.get(create_ns(W_NS, 'numId'))
        if not num_id:
            return
        abstract_id_el = num.find(create_ns(W_NS, 'abstractNumId'))
        if abstract_id_el is None:
            return
        abstract_id = abstract_id_el.get(create_ns(W_NS, 'val'))
        if not abstract_id:
            return
        self.num_to_abstract[str(num_id)] = abstract_id

        levels = dict(abstract_levels.get(abstract_id, {}))

        # Apply lvlOverride: may redefine lvl properties and/or startOverride
        for override in num.findall(create_ns(W_NS, 'lvlOverride')):
            self._apply_level_override(override, levels)

        if levels:
            self.levels[str(num_id)] = levels

    def _apply_level_override(self, override, levels: dict) -> None:
        """Apply a single lvlOverride element to the levels dictionary."""
        ilvl_attr = override.get(create_ns(W_NS, 'ilvl'))
        if ilvl_attr is None:
            return
        try:
            ilvl = int(ilvl_attr)
        except ValueError:
            return

        # startOverride
        self._apply_start_override(override, levels, ilvl)

        # full lvl override
        lvl_el = override.find(create_ns(W_NS, 'lvl'))
        if lvl_el is not None:
            _, info = self._parse_single_level(lvl_el)
            levels[ilvl] = info

    @staticmethod
    def _apply_start_override(override, levels: dict, ilvl: int) -> None:
        """Apply a startOverride element to the level info."""
        start_override_el = override.find(create_ns(W_NS, 'startOverride'))
        if start_override_el is None:
            return
        start_val = start_override_el.get(create_ns(W_NS, 'val'))
        if start_val is None:
            return
        info = levels.setdefault(ilvl, {
            'lvlText': None,
            'numFmt': 'decimal',
            'start': 1,
            'suffix': '',
            'restart': None,
        })
        try:
            info['start'] = int(start_val)
        except ValueError:
            pass

    def _parse_abstract_levels(self, abstract_elem) -> Dict[int, Dict[str, Union[str, int, None]]]:
        levels: Dict[int, Dict[str, Union[str, int, None]]] = {}
        for lvl in abstract_elem.findall(create_ns(W_NS, 'lvl')):
            ilvl, info = self._parse_single_level(lvl)
            levels[ilvl] = info
        return levels

    @staticmethod
    def _parse_single_level(lvl_el) -> Tuple[int, Dict[str, Union[str, int, None]]]:
        ilvl_raw = lvl_el.get(create_ns(W_NS, 'ilvl'))
        try:
            ilvl = int(ilvl_raw) if ilvl_raw is not None else 0
        except ValueError:
            ilvl = 0

        # lvlText
        lvl_text_el = lvl_el.find(create_ns(W_NS, 'lvlText'))
        lvl_text = (lvl_text_el.get(create_ns(W_NS, 'val')) if lvl_text_el is not None else None)

        # numFmt
        fmt_el = lvl_el.find(create_ns(W_NS, 'numFmt'))
        num_fmt = (fmt_el.get(create_ns(W_NS, 'val')) if fmt_el is not None else 'decimal')

        # start
        start_el = lvl_el.find(create_ns(W_NS, 'start'))
        start = 1
        if start_el is not None:
            v = start_el.get(create_ns(W_NS, 'val'))
            try:
                start = int(v) if v is not None else 1
            except ValueError:
                start = 1

        # suffix
        suff_el = lvl_el.find(create_ns(W_NS, 'suff'))
        suffix = (suff_el.get(create_ns(W_NS, 'val')) if suff_el is not None else '')

        # lvlRestart
        restart_el = lvl_el.find(create_ns(W_NS, 'lvlRestart'))
        restart = None
        if restart_el is not None:
            rv = restart_el.get(create_ns(W_NS, 'val'))
            try:
                restart = int(rv) if rv is not None else None
            except ValueError:
                restart = None

        info: Dict[str, Union[str, int, None]] = {
            'lvlText': lvl_text,
            'numFmt': num_fmt,
            'start': start,
            'suffix': suffix,
            'restart': restart,
        }
        return ilvl, info

    @staticmethod
    def _int_to_alpha(value: int, uppercase: bool = False) -> str:
        if value <= 0:
            return str(value)
        result = []
        remaining = value
        while remaining > 0:
            remaining, rem = divmod(remaining - 1, 26)
            base = ord('A') if uppercase else ord('a')
            result.append(chr(base + rem))
        return ''.join(reversed(result))

    @staticmethod
    def _int_to_roman(value: int, uppercase: bool = True) -> str:
        if value <= 0:
            return str(value)
        numerals = [
            (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
            (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
            (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
        ]
        out = []
        remaining = value
        for arabic, roman in numerals:
            while remaining >= arabic:
                out.append(roman)
                remaining -= arabic
        rendered = ''.join(out)
        return rendered if uppercase else rendered.lower()

    def _format_value(self, value: Optional[int], fmt: Optional[str]) -> str:
        if value is None:
            return ''

        f = (fmt or 'decimal').lower()

        # Use dictionary mapping for format handlers
        format_handlers = {
            'decimal': lambda v: str(v),
            'decimalzero': lambda v: str(v),
            'lowerletter': lambda v: self._int_to_alpha(v, uppercase=False),
            'loweralpha': lambda v: self._int_to_alpha(v, uppercase=False),
            'upperletter': lambda v: self._int_to_alpha(v, uppercase=True),
            'upperalpha': lambda v: self._int_to_alpha(v, uppercase=True),
            'lowerroman': lambda v: self._int_to_roman(v, uppercase=False),
            'upperroman': lambda v: self._int_to_roman(v, uppercase=True),
            'bullet': lambda v: '•',
        }

        handler = format_handlers.get(f)
        return handler(value) if handler else str(value)

    def _render_level_text(self, num_id: str, ilvl: int, counters: Dict[int, int]) -> Optional[str]:
        level_map = self.levels.get(num_id, {})
        level_info = level_map.get(ilvl)
        if not level_info:
            return None
        tmpl = level_info.get('lvlText')
        if not tmpl:
            return self._format_value(counters.get(ilvl), str(level_info.get('numFmt')))

        def repl(m: re.Match) -> str:
            """Replace placeholders in the level text template."""
            # %1 -> ilvl 0
            idx = int(m.group(1)) - 1
            val = counters.get(idx)
            fmt = level_map.get(idx, {}).get('numFmt') if idx in level_map else 'decimal'
            return self._format_value(val, str(fmt) if fmt is not None else 'decimal')

        return LVL_TEXT_PATTERN.sub(repl, str(tmpl))

    def get_marker(self, num_id: str, ilvl: int) -> str:
        """Return the marker string for a given numId + level, updating counters correctly."""

        level_map = self.levels.get(num_id)
        if not level_map or ilvl not in level_map:
            return "•"

        level_info = level_map[ilvl]
        start_int = self._safe_start_int(level_info.get('start', 1))

        abstract_id = self.num_to_abstract.get(num_id)
        abstract_state = self.abstract_counters[abstract_id] if abstract_id else None
        counters = self.counters[num_id]

        self._reset_deeper_levels(counters, abstract_state, ilvl)
        self._init_parent_levels(counters, abstract_state, level_map, ilvl)
        self._increment_and_sync_level(counters, abstract_state, ilvl, start_int)

        rendered = self._render_level_text(num_id, ilvl, counters)
        if not rendered:
            rendered = self._format_value(counters.get(ilvl), str(level_info.get('numFmt')))

        return self._format_marker_with_suffix(rendered, level_info)

    @staticmethod
    def _safe_start_int(start) -> int:
        """Safely convert start value to int, defaulting to 1."""
        try:
            return int(start) if start is not None else 1
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _reset_deeper_levels(counters: dict, abstract_state, ilvl: int) -> None:
        """Drop counter entries for levels deeper than ilvl."""
        for k in list(counters.keys()):
            if k > ilvl:
                counters.pop(k, None)
        if abstract_state is not None:
            for k in list(abstract_state.keys()):
                if k > ilvl:
                    abstract_state.pop(k, None)

    def _init_parent_levels(self, counters: dict, abstract_state, level_map: dict, ilvl: int) -> None:
        """Ensure parent levels exist in counters, inheriting from shared abstract state.

        When multiple numIds share the same abstractNumId, they should share counter state.
        Prioritize reading from abstract_state to inherit shared counters.
        """
        for parent in range(ilvl):
            if parent not in counters:
                # First try to inherit from shared abstract state
                if abstract_state is not None and parent in abstract_state:
                    counters[parent] = abstract_state[parent]
                else:
                    # Fall back to pstart only when no shared state exists
                    pinfo = level_map.get(parent, {})
                    counters[parent] = self._safe_start_int(pinfo.get('start', 1))
            elif abstract_state is not None and parent in abstract_state:
                # Sync stale per-numId parent counter from the shared abstract state.
                counters[parent] = abstract_state[parent]
            if abstract_state is not None:
                abstract_state[parent] = counters[parent]

    @staticmethod
    def _increment_and_sync_level(counters: dict, abstract_state, ilvl: int, start_int: int) -> None:
        """Increment the current level counter and sync with abstract state."""
        if ilvl not in counters:
            counters[ilvl] = start_int
        else:
            counters[ilvl] += 1
        # Keep continuity across numIds that share abstractNumId
        if abstract_state is not None:
            prev = abstract_state.get(ilvl)
            if prev is not None and prev + 1 > counters[ilvl]:
                counters[ilvl] = prev + 1
            abstract_state[ilvl] = counters[ilvl]

    @staticmethod
    def _format_marker_with_suffix(rendered, level_info) -> str:
        """Format the rendered marker with appropriate suffix."""
        suffix = str(level_info.get('suffix') or '').lower()
        if suffix in {'space', 'tab'}:
            return f"{rendered} "
        return str(rendered)

class DocxParser(object):
    """Parse DOCX files directly from XML without python-docx."""
    _REVISION_DELETE_LOCALNAMES = frozenset({"del", "cellDel", "rowDel", "tblDel", "moveFrom"})
    _DELETE_OVERLAY_TEXT_PATTERNS = (
        "仕様記載削除",
        "削除",
        "廃止",
        "DEPRECATED",
        "DELETED",
        "REMOVED",
    )

    def __init__(
        self,
        get_table_content: bool = True,
        get_image_content: bool = True,
        get_shape_content: bool = True,
        keep_strikethrough_text: bool = False,
        drop_deleted_table_content: bool = False,
    ):
        self.get_table_content = get_table_content
        self.get_image_content = get_image_content
        self.get_shape_content = get_shape_content
        self.keep_strikethrough_text = keep_strikethrough_text
        self.drop_deleted_table_content = drop_deleted_table_content
        self._numbering_helper: Optional[NumberingHelper] = None
        self._strike_style_ids: Set[str] = set()
        self._style_to_heading_level: Dict[str, int] = {}
        # Store bookmarks and track changes for OfficeDocBench evaluation
        self._bookmarks: List[Dict[str, Any]] = []
        self._track_changes: List[Dict[str, Any]] = []

        # Style -> (numId, ilvl) mapping for styles that have numbering defined
        self._style_to_numpr: Dict[str, Tuple[str, int]] = {}

        # Style IDs that are ToC styles (based on style name matching "toc \d+" pattern)
        self._style_to_toc: Set[str] = set()
        self._image_counter = 0
        self._image_dir: Optional[str] = None
        self._saved_images: List[str] = []

        # Heading counters for manual numbering (when numPr is not present)
        # Index 0 = Heading1, Index 1 = Heading2, etc.
        self._heading_counters: List[int] = [0] * 9
        self._toc_numbering_map: Dict[str, str] = {}
        self._has_toc: bool = False
        # True when document.xml contains Word field instructions (e.g. SEQ),
        # meaning numbering is likely auto-generated and can be normalized.
        self._auto_caption_numbering_detected: bool = False

        self.gray_brightness_thr = 180.0
        self.gray_spread_thr = 12
        self.white_text_ratio_cutoff = 0.98

        self._theme_resolver = ThemeResolver(None)
        self._table_style_helper = None

        # Cache: rel_id -> (saved_path, full_md5)
        self._image_cache_by_rid: Dict[str, Tuple[str, str]] = {}

        # Cache: full_md5 -> saved_path (dedupe across different rel_ids with same bytes)
        self._image_cache_by_hash: Dict[str, str] = {}


    @staticmethod
    def _detect_and_convert_doc(path: Path, temp_dir: Path) -> Path:
        """Convert legacy .doc format to .docx using LibreOffice.

        Returns the path to the converted .docx file inside *temp_dir*.
        The caller is responsible for cleaning up *temp_dir*.
        """
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "docx",
             "--outdir", str(temp_dir), str(path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice .doc→.docx conversion failed: {result.stderr}")
        converted = temp_dir / (path.stem + ".docx")
        if not converted.exists():
            raise FileNotFoundError(f"Converted file not found: {converted}")
        return converted

    def extract_docx_text(
        self,
        docx_path: str,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract content from a DOCX (or legacy .doc) file.

        If the input is a .doc file, it is first converted to .docx via
        LibreOffice, then parsed normally.  Returns a hierarchical tree
        structure with headings and content.
        """
        original_path = Path(docx_path)
        temp_dir_obj = None

        # Legacy .doc → convert to .docx first
        if original_path.suffix.lower() == ".doc":
            temp_dir_obj = Path(tempfile.mkdtemp(prefix="doc2docx_"))
            try:
                converted = self._detect_and_convert_doc(original_path, temp_dir_obj)
                docx_path = str(converted)
            except Exception:
                shutil.rmtree(temp_dir_obj, ignore_errors=True)
                raise

        try:
            return self._extract_docx_text_inner(docx_path, output_dir)
        finally:
            if temp_dir_obj is not None:
                shutil.rmtree(temp_dir_obj, ignore_errors=True)

    def _extract_docx_text_inner(
        self,
        docx_path: str,
        output_dir: Optional[str] = None,
    ) -> List[dict]:
        """Core extraction logic for a .docx file (already in OOXML format)."""
        try:
            with zipfile.ZipFile(docx_path, 'r') as docx_zip:
                document_xml = docx_zip.read(DOCX_DOC_XML)

                numbering_xml = None
                try:
                    numbering_xml = docx_zip.read(DOCX_NUMBERING_XML)
                except KeyError:
                    pass

                styles_xml = None
                try:
                    styles_xml = docx_zip.read(DOCX_STYLES_XML)
                except KeyError:
                    pass

                theme1_xml = None
                try:
                    theme1_xml = docx_zip.read(DOCX_THEME1_XML)
                except KeyError:
                    pass

                rels = {}
                try:
                    rels_xml = docx_zip.read(DOCX_RELS_DOCUMENT)
                    rels = self._parse_relationships(rels_xml)
                except KeyError:
                    pass

                self._numbering_helper = NumberingHelper(numbering_xml)
                if styles_xml:
                    self._parse_styles(styles_xml)
                    self._table_style_helper = TableStyleHelper(styles_xml)
                else:
                    self._table_style_helper = None

                self._theme_resolver = ThemeResolver(theme1_xml)
                self._auto_caption_numbering_detected = self._detect_auto_caption_numbering_fields(document_xml)

                # Parse document
                result = self._parse_document(document_xml, docx_zip, rels, output_dir)

                tree = result.get("content_tree", [])
                # Post-process the tree
                self._postprocess_tree(tree)

                return result

        except Exception as e:
            log.error(f"Failed to parse DOCX: {e}")
            raise

    # Post-processing helpers

    # Used for heading_text: remove any shape blocks entirely.
    _SHAPE_RE = re.compile(
        r"\s*\[START_SHAPE_CONTENT\].*?\[END_SHAPE_CONTENT\]\s*",
        re.DOTALL
    )

    # Used for content: detect individual shape blocks so we can selectively drop them.
    _SHAPE_BLOCK_RE = re.compile(
        rf"{re.escape(SHAPE_CONTENT_START_MARKER)}\s*(.*?)\s*{re.escape(SHAPE_CONTENT_END_MARKER)}",
        re.DOTALL
    )

    # Drop "triangle + single Latin letter" markers like ▲a / ▲ａ / ▲J / ▲ｚ
    _TRIANGLE_SINGLE_LETTER_RE = re.compile(
        r"^[▲△▽▼]\s*[A-Za-zＡ-Ｚａ-ｚ]$"
    )

    # Match [START_IMAGE_PATH] ... [END_IMAGE_PATH] markers inside cell text.
    _IMG_MARKER_RE = re.compile(
        rf"{re.escape(IMG_PATH_START_MARKER)}.*?{re.escape(IMG_PATH_END_MARKER)}",
        re.DOTALL,
    )

    # Figure/table caption prefixes used to identify image-display tables.
    _FIGURE_CAPTION_RE = re.compile(
        r"^\s*(?:図|Figure|Fig\.?|表|Table|Tab\.?)",
        re.IGNORECASE,
    )

    # Caption line pattern used for Word-like chapter-restart numbering simulation.
    # Examples matched:
    #   "Table. 3-3 Terms"
    #   "Figure 4-12 ..."
    #   "表 2-1 ..."
    _CAPTION_LINE_RE = re.compile(
        r"^(?P<prefix>\s*(?:Table|Tab\.?|Figure|Fig\.?|表|図)\.?\s*)"
        r"(?P<chapter>\d+)\s*(?P<sep>[-－‐‑–—])\s*(?P<seq>\d+)"
        r"(?P<suffix>(?:\s|\u3000).*)?$",
        re.IGNORECASE,
    )

    # Heading prefix like "3", "3.", "3.1", "3-1" used to infer chapter number.
    _HEADING_CHAPTER_PREFIX_RE = re.compile(r"^\s*(\d+)(?:[.．\-‐‑–—]\d+)*(?:[.．])?\s*")

    def _postprocess_tree(self, nodes: List[dict]) -> None:
        """Apply post-processing fixes to the parsed heading tree.
        1. Strip [START_SHAPE_CONTENT]...[END_SHAPE_CONTENT] from heading_text.
        2. In node["content"], drop ONLY junk shape-marker blocks like:
        [START_SHAPE_CONTENT] ▲a [END_SHAPE_CONTENT]
        (triangle + single Latin letter; halfwidth or fullwidth)
        3. Normalize child heading levels so that the shallowest child of a
        parent is exactly parent_level + 1 (and deeper children shift
        proportionally).
        4. Simulate Word/SharePoint chapter-restart caption numbering
        (e.g. Table 3-1) for LibreOffice-converted DOCX where SEQ \\s switch
        is not materialized.
        """
        for node in nodes:
            self._postprocess_single_node(node)

        # Second pass in reading order: normalize caption sequence only when
        # the source document shows auto-numbering fields (SEQ). For manually
        # typed captions (plain text), preserve user-entered numbering.
        if self._auto_caption_numbering_detected:
            self._apply_word_style_chapter_restart_numbering(nodes)

    def _postprocess_single_node(self, node: dict) -> None:
        """Process a single node: clean markers and normalize child levels."""
        # Strip shape content markers from heading_text
        ht = node.get("heading_text", "")
        if SHAPE_CONTENT_START_MARKER in ht:
            node["heading_text"] = self._SHAPE_RE.sub("", ht).strip()

        # Drop triangle+letter marker shape blocks from content
        ct = node.get("content", "")
        if isinstance(ct, str) and SHAPE_CONTENT_START_MARKER in ct:
            node["content"] = self._clean_content_shape_markers(ct)

        children = node.get("children", [])
        if not children:
            return

        # Normalize child heading levels
        parent_level = node.get("heading_level", 0)
        child_levels = [c.get("heading_level", 0) for c in children]
        min_child = min(child_levels)
        gap = min_child - (parent_level + 1)
        if gap > 0:
            self._shift_heading_levels(children, -gap)

        # Recurse into children
        self._postprocess_tree(children)

    def _clean_content_shape_markers(self, text: str) -> str:
        """Remove trivial shape-marker blocks from content text.

        Removes shape blocks delimited by SHAPE_CONTENT_START_MARKER/SHAPE_CONTENT_END_MARKER
        that consist only of small junk markers (e.g. a triangle + single Latin letter).
        Also normalizes surrounding whitespace and collapses excessive blank lines.
        """
        if not text or SHAPE_CONTENT_START_MARKER not in text:
            return text

        def repl(m: re.Match) -> str:
            """Replace trivial shape marker blocks with empty strings."""
            inner = (m.group(1) or "").strip()
            if self._TRIANGLE_SINGLE_LETTER_RE.match(inner):
                return ""
            return m.group(0)

        out = self._SHAPE_BLOCK_RE.sub(repl, text)
        out = re.sub(r"[ \t]+\n", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()

    def _shift_heading_levels(self, nodes: List[dict], delta: int) -> None:
        """Shift heading_level of nodes (and all descendants) by delta."""
        for node in nodes:
            node["heading_level"] = node.get("heading_level", 0) + delta
            children = node.get("children", [])
            if children:
                self._shift_heading_levels(children, delta)

    # ---------- Word-style chapter restart numbering simulation ----------

    @staticmethod
    def _detect_auto_caption_numbering_fields(document_xml: bytes) -> bool:
        """Return True when document has Word field instructions for numbering.

        We treat this as an "automatic numbering" signal and enable chapter-restart
        normalization only in this case. Manually typed caption numbers should be
        left untouched.
        """
        detected = False
        try:
            root = etree.fromstring(document_xml) if document_xml else None
        except Exception:
            root = None

        if root is not None:
            for instr in root.findall(f".//{create_ns(W_NS, 'instrText')}"):
                txt = "".join(instr.itertext()).strip().upper()
                if "SEQ" in txt:
                    detected = True
                    break
        return detected

    @staticmethod
    def _caption_kind_from_prefix(prefix: str) -> str:
        """Normalize caption label to a sequence family key (table/figure)."""
        p = (prefix or "").strip().lower().rstrip(".")
        if p in {"table", "tab", "表"}:
            return "table"
        if p in {"figure", "fig", "図"}:
            return "figure"
        return "other"

    def _extract_chapter_from_heading_text(self, heading_text: str) -> Optional[int]:
        """Extract chapter number from heading text prefix."""
        chapter = None
        if heading_text:
            m = self._HEADING_CHAPTER_PREFIX_RE.match(heading_text)
            if m:
                try:
                    chapter = int(m.group(1))
                except (TypeError, ValueError):
                    chapter = None
        return chapter

    def _renumber_caption_lines_for_chapter(
        self,
        text: str,
        chapter_hint: Optional[int],
        chapter_seq_state: Dict[int, Dict[str, int]],
    ) -> str:
        """Renumber caption lines to restart by chapter (Word-like behavior)."""
        if not isinstance(text, str) or not text:
            return text

        out_lines: List[str] = []
        lines = text.split("\n")

        for line in lines:
            m = self._CAPTION_LINE_RE.match(line)
            if not m:
                out_lines.append(line)
                continue

            prefix = m.group("prefix") or ""
            suffix = m.group("suffix") or ""
            sep = m.group("sep") or "-"

            try:
                detected_chapter = int(m.group("chapter"))
            except (TypeError, ValueError):
                out_lines.append(line)
                continue

            chapter = chapter_hint if chapter_hint is not None else detected_chapter
            kind = self._caption_kind_from_prefix(prefix)
            chapter_state = chapter_seq_state.setdefault(chapter, {})
            next_seq = chapter_state.get(kind, 0) + 1
            chapter_state[kind] = next_seq

            out_lines.append(f"{prefix}{chapter}{sep}{next_seq}{suffix}")

        return "\n".join(out_lines)

    def _apply_word_style_chapter_restart_numbering(self, nodes: List[dict]) -> None:
        """Apply chapter-restart caption numbering in depth-first reading order."""
        chapter_seq_state: Dict[int, Dict[str, int]] = {}

        def walk(node_list: List[dict], active_chapter: Optional[int]) -> None:
            """Depth-first traversal that renumbers caption lines in reading order."""
            chapter = active_chapter
            for n in node_list:
                # For Word's "restart by chapter", chapter anchor is Heading 1.
                if int(n.get("heading_level", 0) or 0) == 1:
                    chapter = self._extract_chapter_from_heading_text(
                        str(n.get("heading_text", "") or "")
                    ) or chapter

                content = n.get("content")
                if isinstance(content, str) and content:
                    n["content"] = self._renumber_caption_lines_for_chapter(
                        content,
                        chapter,
                        chapter_seq_state,
                    )

                children = n.get("children", [])
                if children:
                    walk(children, chapter)

        walk(nodes, None)

    @staticmethod
    def _parse_relationships(rels_xml: bytes) -> Dict[str, str]:
        """Parse relationship IDs to targets."""
        rels = {}
        try:
            root = etree.fromstring(rels_xml)
            for rel in root.findall(create_ns(PKG_REL_NS, "Relationship")):
                rel_id = rel.get("Id")
                target = rel.get("Target")
                if rel_id and target:
                    rels[rel_id] = target
        except Exception as e:
            log.warning(f"Failed to parse relationships: {e}")
        return rels

    def _parse_styles(self, styles_xml: bytes) -> None:
        """Parse styles.xml to extract heading levels, strikethrough styles, numPr definitions, and ToC styles."""
        try:
            root = etree.fromstring(styles_xml)
        except Exception as e:
            log.warning(f"Failed to parse styles: {e}")
            return

        try:
            self._process_all_styles(root)
        except Exception as e:
            log.warning(f"Failed to process styles: {e}")

    def _process_all_styles(self, root) -> None:
        """Process all style elements from parsed styles.xml root."""
        style_name_map: Dict[str, str] = {}
        style_alias_map: Dict[str, str] = {}
        style_based_on: Dict[str, str] = {}
        style_outline_lvl: Dict[str, int] = {}
        styles_with_ilvl_only: Dict[str, int] = {}

        for style in root.findall(create_ns(W_NS, "style")):
            style_id = style.get(create_ns(W_NS, "styleId"))
            if not style_id:
                continue
            self._process_single_style_element(
                style, style_id,
                style_name_map, style_alias_map,
                style_based_on, style_outline_lvl,
                styles_with_ilvl_only,
            )

        self._resolve_numid_inheritance(styles_with_ilvl_only, style_based_on)
        self._resolve_all_heading_levels(
            style_name_map, style_alias_map,
            style_based_on, style_outline_lvl,
        )

    def _process_single_style_element(
        self,
        style,
        style_id: str,
        style_name_map: Dict[str, str],
        style_alias_map: Dict[str, str],
        style_based_on: Dict[str, str],
        style_outline_lvl: Dict[str, int],
        styles_with_ilvl_only: Dict[str, int],
    ) -> None:
        """Process a single w:style element during styles.xml parsing."""
        # 1. ToC indicator
        self._extract_toc_indicator(style, style_id)

        # 2. Paragraph style metadata
        if style.get(create_ns(W_NS, "type")) == "paragraph":
            self._extract_paragraph_metadata(
                style, style_id,
                style_name_map, style_alias_map,
                style_based_on, style_outline_lvl,
            )

        # 3. Strike detection
        self._extract_strike_info(style, style_id)

        # 4. numPr extraction
        self._extract_numpr_info(style, style_id, styles_with_ilvl_only)

    def _extract_toc_indicator(self, style, style_id: str) -> None:
        """Check if style is a ToC style and register it."""
        name_el = style.find(create_ns(W_NS, "name"))
        if name_el is None:
            return
        name_val = name_el.get(create_ns(W_NS, "val"))
        if name_val and re.match(r"toc\s*\d+", name_val, re.IGNORECASE):
            self._style_to_toc.add(style_id)

    def _extract_paragraph_metadata(
        self,
        style,
        style_id: str,
        style_name_map: Dict[str, str],
        style_alias_map: Dict[str, str],
        style_based_on: Dict[str, str],
        style_outline_lvl: Dict[str, int],
    ) -> None:
        """Extract paragraph style metadata (name, aliases, basedOn, outlineLvl)."""
        # name
        name_el = style.find(create_ns(W_NS, "name"))
        if name_el is not None:
            name_val = name_el.get(create_ns(W_NS, "val"))
            if name_val:
                style_name_map[style_id] = name_val

        # aliases (comma-separated display aliases)
        aliases_el = style.find(create_ns(W_NS, "aliases"))
        if aliases_el is not None:
            aliases_val = aliases_el.get(create_ns(W_NS, "val"))
            if aliases_val:
                style_alias_map[style_id] = aliases_val

        # basedOn
        based_el = style.find(create_ns(W_NS, "basedOn"))
        if based_el is not None:
            base_id = based_el.get(create_ns(W_NS, "val"))
            if base_id:
                style_based_on[style_id] = base_id

        # outlineLvl inside the style's pPr
        outline_lvl = self._extract_outline_level_from_style(style)
        if outline_lvl is not None:
            style_outline_lvl[style_id] = outline_lvl

    @staticmethod
    def _extract_outline_level_from_style(style) -> Optional[int]:
        """Extract outlineLvl from a style's pPr if present."""
        ppr = style.find(create_ns(W_NS, "pPr"))
        out = ppr.find(create_ns(W_NS, "outlineLvl")) if ppr is not None else None
        v = out.get(create_ns(W_NS, "val")) if out is not None else None
        if v is None:
            return None
        try:
            oi = int(v)
            return oi if 0 <= oi <= 8 else None
        except ValueError:
            return None

    def _extract_strike_info(self, style, style_id: str) -> None:
        """Check if style has strikethrough and register it.

        Only checks direct rPr children, NOT inside rPrChange (revision tracking).
        """
        style_rpr = style.find(create_ns(W_NS, "rPr"))
        if style_rpr is None:
            return
        if _elem_has_any_child(style_rpr, W_NS, "strike", "dstrike"):
            self._strike_style_ids.add(style_id)

    def _extract_numpr_info(self, style, style_id: str, styles_with_ilvl_only: Dict[str, int]) -> None:
        """Extract numPr (numbering properties) from style's pPr."""
        ppr = style.find(create_ns(W_NS, "pPr"))
        if ppr is None:
            return
        numpr = ppr.find(create_ns(W_NS, "numPr"))
        if numpr is None:
            return

        num_id_el = numpr.find(create_ns(W_NS, "numId"))
        ilvl_el = numpr.find(create_ns(W_NS, "ilvl"))
        ilvl = self._parse_ilvl_value(ilvl_el)

        num_id = num_id_el.get(create_ns(W_NS, "val")) if num_id_el is not None else None
        if num_id:
            self._style_to_numpr[style_id] = (num_id, ilvl)
        elif ilvl_el is not None:
            # Style has ilvl but no numId – record partial info
            # so we can inherit numId from basedOn parent below.
            styles_with_ilvl_only[style_id] = ilvl

    @staticmethod
    def _parse_ilvl_value(ilvl_el) -> int:
        """Parse ilvl element value, defaulting to 0."""
        ilvl_val = ilvl_el.get(create_ns(W_NS, "val")) if ilvl_el is not None else None
        if not ilvl_val:
            return 0
        try:
            return int(ilvl_val)
        except ValueError:
            return 0

    def _resolve_numid_inheritance(
        self, styles_with_ilvl_only: Dict[str, int], style_based_on: Dict[str, str]
    ) -> None:
        """Resolve numId inheritance for styles that only specify ilvl.

        Word allows a child style to specify only ilvl in numPr and inherit
        the numId from its basedOn parent style.
        """
        for sid, ilvl_val in styles_with_ilvl_only.items():
            inherited_num_id = self._find_inherited_numid(sid, style_based_on, set())
            if inherited_num_id:
                self._style_to_numpr[sid] = (inherited_num_id, ilvl_val)

    def _find_inherited_numid(
        self, sid: str, style_based_on: Dict[str, str], seen: Set[str]
    ) -> Optional[str]:
        """Walk the basedOn chain to find an inherited numId."""
        if sid in seen:
            return None
        seen.add(sid)
        existing = self._style_to_numpr.get(sid)
        if existing:
            return existing[0]
        parent = style_based_on.get(sid)
        return self._find_inherited_numid(parent, style_based_on, seen) if parent else None

    def _resolve_all_heading_levels(
        self,
        style_name_map: Dict[str, str],
        style_alias_map: Dict[str, str],
        style_based_on: Dict[str, str],
        style_outline_lvl: Dict[str, int],
    ) -> None:
        """Resolve heading levels for all paragraph styles.

        Priority:
        1) style pPr/outlineLvl
        2) styleId pattern HeadingN
        3) basedOn chain
        4) name/aliases fallback (supports EN + JP keyword "見出し")
        """
        heading_id_pat = re.compile(r"^Heading\s*([1-9])$", re.IGNORECASE)
        heading_name_pat = re.compile(r"(heading|見出し)\s*([1-9])", re.IGNORECASE)

        all_para_style_ids = (
            set(style_name_map.keys()) | set(style_based_on.keys()) | set(style_outline_lvl.keys())
        )
        style_ctx = (style_name_map, style_alias_map, style_based_on, style_outline_lvl)
        for sid in all_para_style_ids:
            lvl = self._resolve_single_heading_level(
                sid, set(), style_ctx,
                heading_id_pat, heading_name_pat,
            )
            if lvl is not None:
                self._style_to_heading_level[sid] = lvl

    def _resolve_single_heading_level(
        self,
        sid: str,
        visiting: Set[str],
        style_ctx: tuple,
        heading_id_pat,
        heading_name_pat,
    ) -> Optional[int]:
        """Resolve heading level for a single style ID.

        style_ctx is a tuple of (style_name_map, style_alias_map, style_based_on, style_outline_lvl).
        """
        if not sid or sid in visiting:
            return None
        if sid in self._style_to_heading_level:
            return self._style_to_heading_level[sid]
        visiting.add(sid)

        style_name_map, style_alias_map, style_based_on, style_outline_lvl = style_ctx

        # (1) outlineLvl on style
        if sid in style_outline_lvl:
            return style_outline_lvl[sid] + 1

        # (2) styleId looks like Heading1/Heading2/...
        m = heading_id_pat.match(sid)
        if m:
            return int(m.group(1))

        # (3) basedOn inheritance
        base = style_based_on.get(sid)
        if base:
            lvl = self._resolve_single_heading_level(base, visiting, style_ctx, heading_id_pat, heading_name_pat)
            if lvl is not None:
                return lvl

        # (4) fallback: name / aliases contains "heading N" or "見出し N"
        return self._heading_level_from_name_alias(
            sid, style_name_map, style_alias_map, heading_name_pat
        )

    @staticmethod
    def _heading_level_from_name_alias(
        sid: str,
        style_name_map: Dict[str, str],
        style_alias_map: Dict[str, str],
        heading_name_pat,
    ) -> Optional[int]:
        """Try to extract heading level from style name or aliases."""
        nm = style_name_map.get(sid, "")
        al = style_alias_map.get(sid, "")
        blob = f"{nm} {al}".strip()
        m2 = heading_name_pat.search(blob)
        if m2:
            try:
                return int(m2.group(2))
            except ValueError:
                pass
        return None

    def _process_p_element(
        self,
        children: List,
        i: int,
        stack: List,
        tree: List,
        pending_drawing_ps: List,
        overlay_suppress_active: bool,
        overlay_suppress_level: Optional[int],
    ) -> Tuple[int, bool, Optional[int]]:
        """Handle a <w:p> element in the main body loop.

        Returns (advance_by, new_overlay_active, new_overlay_level).
        advance_by is always >= 1.
        """
        child = children[i]
        p_has_overlay = self._paragraph_has_opaque_front_overlay(child)

        # Activate overlay suppression on first opaque overlay paragraph.
        if p_has_overlay and not overlay_suppress_active:
            overlay_suppress_level = self._determine_overlay_suppress_level(child, stack)
            overlay_suppress_active = True

        # While suppressed: lift suppression at a heading equal/above the anchor level,
        # or skip the paragraph entirely.
        if overlay_suppress_active:
            _hlvl = self._peek_heading_level(child)
            if _hlvl is not None and _hlvl <= overlay_suppress_level and not p_has_overlay:
                # This heading is at or above the suppression level & NOT carrying an overlay -> reset.
                overlay_suppress_active = False
                overlay_suppress_level = None
            else:
                # Still suppressed – skip this paragraph entirely.
                pending_drawing_ps.clear()
                return 1, overlay_suppress_active, overlay_suppress_level

        # Buffer drawing-only paragraphs for cluster processing.
        if self._is_drawing_only_paragraph(child) or (
            pending_drawing_ps and self._is_effectively_empty_paragraph(child)
        ):
            pending_drawing_ps.append(child)
            return 1, overlay_suppress_active, overlay_suppress_level

        # Hybrid: visible text + anchored drawing that should feed the drawing buffer.
        if not (
            not pending_drawing_ps
            and self._paragraph_has_visible_text_outside_textbox(child)
            and self._has_body_level_anchored_drawing(child)
            and self._try_handle_hybrid_paragraph(child, children, i, stack, pending_drawing_ps)
        ):
            # Normal paragraph: flush any buffered drawings first.
            self._flush_pending_drawing_ps(pending_drawing_ps, stack)
            self._handle_normal_paragraph(child, stack, tree)

        return 1, overlay_suppress_active, overlay_suppress_level

    def _process_tbl_element(
        self,
        children: List,
        i: int,
        stack: List,
        pending_drawing_ps: List,
        overlay_suppress_active: bool,
        tree: List,
    ) -> int:
        """Handle a <w:tbl> element in the main body loop.

        Returns the number of children consumed (always >= 1).
        """
        if overlay_suppress_active:
            pending_drawing_ps.clear()
            return 1
        # Flush before table so buffered diagram doesn't leak past table boundary.
        self._flush_pending_drawing_ps(pending_drawing_ps, stack)
        return max(1, self._handle_table_element(children, i, stack, tree))

    def _parse_document(
        self,
        document_xml: bytes,
        docx_zip: zipfile.ZipFile,
        rels: Dict[str, str],
        output_dir: Optional[str],
    ) -> List[dict]:
        """Parse the main document.xml."""

        self._docx_zip = docx_zip
        self._rels = rels
        self._output_dir = output_dir

        try:
            root = etree.fromstring(document_xml)
        except Exception as e:
            log.error(f"Failed to parse document.xml: {e}")
            return []

        # First pass: extract ToC entries to build numbering ground truth
        self._extract_toc_entries(root)
        # Extract bookmarks and track changes
        self._bookmarks = self._extract_bookmarks(root)
        self._track_changes = self._extract_track_changes(root)
        # Reset heading counters for second pass
        self._heading_counters = [0] * 9

        body = root.find(create_ns(W_NS, "body"))
        if body is None:
            return []

        # (level, node_dict)
        stack = []
        tree = []

        children = list(body)

        # Find the index where main content starts (after ToC and front matter)
        start_index = self._find_content_start_index(children)
        i = start_index

        # ── Body-level overlay suppression ──
        # When a body-level paragraph contains a large opaque front-anchored
        # rectangle we treat all subsequent paragraphs/tables as hidden
        # (analogous to table-cell overlay detection) until the next heading
        # at the overlay-anchor heading level or above resets it.
        overlay_suppress_level: Optional[int] = None
        overlay_suppress_active: bool = False

        # Buffer consecutive drawing-only paragraphs so we can decide "picture cluster"
        # BEFORE emitting any shape text (prevents early labels like ライセンスキー/車載機).
        pending_drawing_ps: List = []

        while i < len(children):
            child = children[i]

            if child.tag == create_ns(W_NS, "p"):
                advance, overlay_suppress_active, overlay_suppress_level = self._process_p_element(
                    children, i, stack, tree, pending_drawing_ps,
                    overlay_suppress_active, overlay_suppress_level,
                )
                i += advance
                continue

            if child.tag == create_ns(W_NS, "tbl"):
                i += self._process_tbl_element(
                    children, i, stack, pending_drawing_ps, overlay_suppress_active, tree
                )
                continue

            if child.tag == create_ns(W_NS, "sdt"):
                # Structured Document Tags (sdt) wrap tables/paragraphs (e.g. use-case
                # scenario tables). Inline-process their sdtContent children so that
                # tables immediately following a heading are not silently dropped.
                self._flush_pending_drawing_ps(pending_drawing_ps, stack)
                sdt_content = child.find(create_ns(W_NS, "sdtContent"))
                if sdt_content is not None:
                    sdt_children = list(sdt_content)
                    sdt_j = 0
                    while sdt_j < len(sdt_children):
                        sdt_child = sdt_children[sdt_j]
                        if sdt_child.tag == create_ns(W_NS, "tbl"):
                            sdt_j += self._process_tbl_element(
                                sdt_children, sdt_j, stack, pending_drawing_ps, overlay_suppress_active, tree
                            )
                        elif sdt_child.tag == create_ns(W_NS, "p"):
                            advance, overlay_suppress_active, overlay_suppress_level = self._process_p_element(
                                sdt_children, sdt_j, stack, tree, pending_drawing_ps,
                                overlay_suppress_active, overlay_suppress_level,
                            )
                            sdt_j += advance
                        else:
                            sdt_j += 1
                i += 1
                continue

            # Other elements: flush pending and move on
            self._flush_pending_drawing_ps(pending_drawing_ps, stack)
            i += 1

        # End of body: flush remaining buffered drawing paragraphs
        self._flush_pending_drawing_ps(pending_drawing_ps, stack)

        # Prune empty nodes
        tree = self._prune_tree(tree)

        # Return dict with content_tree, bookmarks, and track_changes
        return {
            "content_tree": tree,
            "bookmarks": self._bookmarks,
            "track_changes": self._track_changes
        }

    # ---------- _parse_document helper methods ----------

    def _flush_pending_drawing_ps(self, pending_drawing_ps: List, stack: List) -> None:
        """Process and emit buffered drawing-only paragraphs.

        Filters out crossed-out images, detects diagram/image clusters
        and either renders diagram clusters to images or extracts image
        placeholders and substantial shape text.
        """
        if not pending_drawing_ps:
            return

        # Filter out crossed-out image paragraphs
        pending_drawing_ps[:] = [
            p for p in pending_drawing_ps
            if not (self._paragraph_has_image(p)
                    and self._paragraph_image_is_crossed_out(p))
        ]
        if not pending_drawing_ps:
            return

        has_img = any(self._paragraph_has_image(p) for p in pending_drawing_ps)
        drawing_count = sum(1 for p in pending_drawing_ps if self._is_drawing_only_paragraph(p))
        has_rich_anchor = self._detect_rich_anchor(pending_drawing_ps)

        is_cluster = has_img or drawing_count >= 3 or has_rich_anchor
        if is_cluster:
            self._emit_drawing_cluster(
                pending_drawing_ps, stack, has_img, drawing_count, has_rich_anchor
            )
        else:
            self._emit_drawings_normally(pending_drawing_ps, stack)

        pending_drawing_ps.clear()

    @staticmethod
    def _detect_rich_anchor(pending_drawing_ps: List) -> bool:
        """Check if any paragraph has a rich wpg:wgp group with ≥5 wsp shapes."""
        for p in pending_drawing_ps:
            for wrapper in list(p.iter(create_ns(WP_NS, 'anchor'))) + list(p.iter(create_ns(WP_NS, 'inline'))):
                wpg_groups = list(wrapper.iter(create_ns(WPG_NS, 'wgp')))
                if wpg_groups:
                    wsps_in_wrapper = len(list(wrapper.iter(create_ns(WPS_NS, 'wsp'))))
                    if wsps_in_wrapper >= 5:
                        return True
        return False

    def _emit_drawing_cluster(
        self, pending_drawing_ps: List, stack: List,
        has_img: bool, drawing_count: int, has_rich_anchor: bool
    ) -> None:
        """Emit a drawing cluster (diagram or raster images) to the current node."""
        if not stack:
            return
        node = stack[-1][1]

        # Vector-shape diagram cluster
        if (drawing_count >= 3 or has_rich_anchor) and not has_img:
            self._emit_diagram_cluster(node, pending_drawing_ps)
            return

        # Raster-image cluster
        self._emit_raster_cluster(node, pending_drawing_ps)

    def _emit_diagram_cluster(self, node: dict, pending_drawing_ps: List) -> None:
        """Render diagram cluster to images and append to node content."""
        img_placeholders = self._diagram_cluster_to_images(pending_drawing_ps)
        for img_ph in img_placeholders:
            self._append_to_node_content(node, img_ph)
        if "content" in node:
            node["content"] = self._merge_ver_marker(node["content"])

    def _emit_raster_cluster(self, node: dict, pending_drawing_ps: List) -> None:
        """Extract images, shape text, and captions from raster image cluster."""
        for p in pending_drawing_ps:
            # 1) Extract actual images (blips) and emit IMAGE_PATH markers
            for img_ph in self._extract_images_from_paragraph(p):
                self._append_to_node_content(node, img_ph)

            # 2) Extract substantial bordered-shape text
            for st in self._extract_substantial_shape_text_from_paragraph(p):
                block = f"{SHAPE_CONTENT_START_MARKER} {st} {SHAPE_CONTENT_END_MARKER}"
                self._append_to_node_content(node, block)

            # 3) Keep caption-like shape text
            cap = self._extract_caption_text_from_paragraph(p)
            if cap:
                block = f"{SHAPE_CONTENT_START_MARKER} {cap} {SHAPE_CONTENT_END_MARKER}"
                self._append_to_node_content(node, block)

            if "content" in node:
                node["content"] = self._merge_ver_marker(node["content"])

    def _emit_drawings_normally(self, pending_drawing_ps: List, stack: List) -> None:
        """Emit non-clustered drawing paragraphs as normal text."""
        for p in pending_drawing_ps:
            text, _, _ = self._parse_paragraph(p)
            if stack and text:
                self._append_to_node_content(stack[-1][1], text)
                stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])

    @staticmethod
    def _append_to_node_content(node: dict, text: str) -> None:
        """Append text to a node's content, creating the key if needed."""
        if "content" not in node:
            node["content"] = text
        else:
            node["content"] += "\n" + text

    def _determine_overlay_suppress_level(self, p_elem, stack: List) -> int:
        """Determine the heading level to anchor overlay suppression."""
        hlvl = self._peek_heading_level(p_elem)
        if hlvl is not None:
            return hlvl
        if stack:
            return stack[-1][0]
        return 1

    def _try_handle_hybrid_paragraph(
        self, child, children, i: int, stack: List, pending_drawing_ps: List
    ) -> bool:
        """Handle hybrid paragraph with both anchored drawings and visible text.

        Returns True if the paragraph was handled (caller should increment i and continue).
        """
        if i + 1 >= len(children):
            return False
        next_child = children[i + 1]
        if next_child.tag != create_ns(W_NS, "p") or not self._is_drawing_only_paragraph(next_child):
            return False

        # Emit text only (images/shapes suppressed)
        text, _, _ = self._parse_paragraph(child, skip_images=True)
        if stack and text:
            self._append_to_node_content(stack[-1][1], text)
            stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])

        # Buffer a stripped copy (drawings only) for the diagram pipeline.
        p_stripped = deepcopy(child)
        for r_elem in list(p_stripped.findall(create_ns(W_NS, "r"))):
            has_drw = (
                r_elem.find(f".//{create_ns(W_NS, 'drawing')}") is not None
                or r_elem.find(f".//{create_ns(W_NS, 'pict')}") is not None
            )
            if not has_drw:
                p_stripped.remove(r_elem)
        pending_drawing_ps.append(p_stripped)
        return True


    def _handle_table_element(self, children, i: int, stack: List, tree: List) -> int:
        """Handle a table element, returning the number of children consumed."""
        md_blocks, consumed, grid = self._parse_table_chain(children, i)

        # If the table only contains images and figure captions, emit them
        # as standalone image markers + caption text instead of a table block.
        if grid and self.get_table_content and self._is_image_caption_only_grid(grid):
            block = self._format_image_caption_grid(grid)
            if stack:
                self._append_to_node_content(stack[-1][1], block)
                stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])
            else:
                # No heading yet - create implicit root node for
                node = {
                    "heading_text": "",
                    "heading_level": 0,
                    "children": [],
                    "content": ""
                }
                tree.append(node)
                stack.append((0, node))
                self._append_to_node_content(node, block)
                node["content"] = self._merge_ver_marker(node["content"])
        else:
            for table_md in md_blocks:
                block = (
                    f"\n[START_TABLE_CONTENT] {table_md} [END_TABLE_CONTENT]\n"
                    if self.get_table_content
                    else "\n[START_TABLE_CONTENT] TABLE [END_TABLE_CONTENT]\n"
                )
                if stack:
                    self._append_to_node_content(stack[-1][1], block)
                    stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])
                else:
                    # No heading yet - create implicit root node for table content
                    node = {
                        "heading_text": "",
                        "heading_level": 0,
                        "children": [],
                        "content": ""
                    }
                    tree.append(node)
                    stack.append((0, node))
                    self._append_to_node_content(node, block)
                    node["content"] = self._merge_ver_marker(node["content"])
        return consumed

    # ---------- Image-only table helpers ----------

    # Cell type constants for image-caption grid classification.
    _ICG_EMPTY = 0
    _ICG_IMAGE_ONLY = 1
    _ICG_IMAGE_WITH_CAPTION = 2
    _ICG_CAPTION_ONLY = 3

    def _classify_icg_cell(self, text: str) -> int:
        """Classify a single cell for image-caption grid processing."""
        text = text.strip()
        if not text:
            return self._ICG_EMPTY
        if IMG_PATH_START_MARKER in text:
            remaining = self._IMG_MARKER_RE.sub("", text).strip()
            if remaining and self._FIGURE_CAPTION_RE.match(remaining):
                return self._ICG_IMAGE_WITH_CAPTION
            return self._ICG_IMAGE_ONLY if not remaining else self._ICG_IMAGE_WITH_CAPTION
        if self._FIGURE_CAPTION_RE.match(text):
            return self._ICG_CAPTION_ONLY

        # not a valid image/caption cell
        return -1

    def _is_image_caption_only_grid(self, grid: List[List[str]]) -> bool:
        """Return True when every cell in grid is an image marker, a figure
        caption, or empty – and at least one image marker exists.

        This detects tables used purely for layout (positioning figures and
        their captions) so they can be unwrapped into standalone content.
        """
        has_image = False
        for row in grid:
            for cell in row:
                ct = self._classify_icg_cell(cell)
                if ct < 0:
                    return False
                if ct in (self._ICG_IMAGE_ONLY, self._ICG_IMAGE_WITH_CAPTION):
                    has_image = True
        return has_image

    def _format_image_caption_grid(self, grid: List[List[str]]) -> str:
        """Format an image-only grid with intelligent image-caption matching.

        Matching heuristic for each IMAGE_ONLY cell at ``[r][c]``:

        1. Look down in the same column for consecutive CAPTION_ONLY cells.
        2. If nothing is found, look right in the same row.
        3. If still nothing is found, emit the image standalone.

        IMAGE_WITH_CAPTION cells are emitted as-is.
        """
        if not grid:
            return ""

        rect = self._normalize_icg_grid(grid)
        ctype = self._build_icg_cell_types(rect)
        consumed, matched = self._match_icg_captions(rect, ctype)

        return self._render_icg_output(rect, ctype, consumed, matched)

    @staticmethod
    def _normalize_icg_grid(grid: List[List[str]]) -> List[List[str]]:
        """Normalize grid into a rectangular matrix by padding missing cells with empty strings."""
        n_cols = max(len(row) for row in grid)
        return [row + [""] * (n_cols - len(row)) for row in grid]


    def _build_icg_cell_types(self, rect: List[List[str]]) -> List[List[str]]:
        """Classify every cell in the normalized grid."""
        n_rows = len(rect)
        n_cols = len(rect[0]) if rect else 0
        return [
            [self._classify_icg_cell(rect[r][c]) for c in range(n_cols)]
            for r in range(n_rows)
        ]


    def _match_icg_captions(
        self,
        rect: List[List[str]],
        ctype: List[List[str]],
    ) -> Tuple[List[List[bool]], Dict[Tuple[int, int], List[str]]]:
        """Match captions to IMAGE_ONLY cells and mark consumed caption cells.

        Returns
        -------
        consumed:
            Boolean matrix telling whether a cell has already been consumed as a caption.
        matched:
            Mapping from image cell position ``(r, c)`` to list of matched caption strings.
        """
        n_rows = len(rect)
        n_cols = len(rect[0]) if rect else 0

        consumed = [[False] * n_cols for _ in range(n_rows)]
        matched: Dict[Tuple[int, int], List[str]] = {}

        for r in range(n_rows):
            for c in range(n_cols):
                if ctype[r][c] != self._ICG_IMAGE_ONLY:
                    continue

                captions = self._find_icg_captions_for_image(r, c, rect, ctype, consumed)
                matched[(r, c)] = captions

        return consumed, matched


    def _find_icg_captions_for_image(
        self,
        r: int,
        c: int,
        rect: List[List[str]],
        ctype: List[List[str]],
        consumed: List[List[bool]],
    ) -> List[str]:
        """Find captions for one IMAGE_ONLY cell.

        Search order:
        1. Downward in the same column
        2. Rightward in the same row
        """
        captions = self._collect_icg_captions_down(r, c, rect, ctype, consumed)
        if captions:
            return captions

        return self._collect_icg_captions_right(r, c, rect, ctype, consumed)


    def _collect_icg_captions_down(
        self,
        r: int,
        c: int,
        rect: List[List[str]],
        ctype: List[List[str]],
        consumed: List[List[bool]],
    ) -> List[str]:
        """Collect consecutive CAPTION_ONLY cells below ``(r, c)`` in the same column."""
        captions: List[str] = []
        n_rows = len(rect)

        nr = r + 1
        while nr < n_rows and self._is_available_icg_caption_cell(nr, c, ctype, consumed):
            captions.append(rect[nr][c].strip())
            consumed[nr][c] = True
            nr += 1

        return captions


    def _collect_icg_captions_right(
        self,
        r: int,
        c: int,
        rect: List[List[str]],
        ctype: List[List[str]],
        consumed: List[List[bool]],
    ) -> List[str]:
        """Collect consecutive CAPTION_ONLY cells to the right of ``(r, c)`` in the same row."""
        captions: List[str] = []
        n_cols = len(rect[0]) if rect else 0

        nc = c + 1
        while nc < n_cols and self._is_available_icg_caption_cell(r, nc, ctype, consumed):
            captions.append(rect[r][nc].strip())
            consumed[r][nc] = True
            nc += 1

        return captions


    def _is_available_icg_caption_cell(
        self,
        r: int,
        c: int,
        ctype: List[List[str]],
        consumed: List[List[bool]],
    ) -> bool:
        """Return True if the cell is a CAPTION_ONLY cell and has not been consumed yet."""
        return (
            ctype[r][c] == self._ICG_CAPTION_ONLY
            and not consumed[r][c]
        )


    def _render_icg_output(
        self,
        rect: List[List[str]],
        ctype: List[List[str]],
        consumed: List[List[bool]],
        matched: Dict[Tuple[int, int], List[str]],
    ) -> str:
        """Render final output in row-major order."""
        parts: List[str] = []
        n_rows = len(rect)
        n_cols = len(rect[0]) if rect else 0

        for r in range(n_rows):
            for c in range(n_cols):
                if consumed[r][c]:
                    continue

                text = rect[r][c].strip()
                if not text:
                    continue

                self._append_icg_cell_output(parts, r, c, text, ctype, matched)

        return "\n" + "\n".join(parts) + "\n"


    def _append_icg_cell_output(
        self,
        parts: List[str],
        r: int,
        c: int,
        text: str,
        ctype: List[List[str]],
        matched: Dict[Tuple[int, int], List[str]],
    ) -> None:
        """Append one cell's rendered output to the final parts list."""
        cell_type = ctype[r][c]

        if cell_type == self._ICG_IMAGE_ONLY:
            self._append_icg_image_only_output(parts, text, matched.get((r, c), []))
            return

        if cell_type == self._ICG_IMAGE_WITH_CAPTION:
            parts.append(text)
            return

        if cell_type == self._ICG_CAPTION_ONLY:
            parts.append(text)


    def _append_icg_image_only_output(
        self,
        parts: List[str],
        text: str,
        captions: List[str],
    ) -> None:
        """Append image markers and matched captions for one IMAGE_ONLY cell."""
        for img_m in self._IMG_MARKER_RE.finditer(text):
            parts.append(img_m.group(0))

        if captions:
            parts.append("".join(captions))

    def _handle_normal_paragraph(self, child, stack: List, tree: List) -> None:
        """Handle a normal (non-drawing, non-table) paragraph."""
        text, heading_level, heading_text = self._parse_paragraph(child)
        if heading_level and heading_text:
            node = {
                "heading_text": heading_text,
                "heading_level": int(heading_level),
                "children": []
            }
            while stack and stack[-1][0] >= int(heading_level):
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                tree.append(node)
            stack.append((int(heading_level), node))
        elif stack and text:
            self._append_to_node_content(stack[-1][1], text)
            stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])
        elif not stack and text:
            # First text element without a prior heading -> create an implicit root node
            node = {
                "heading_text": "",
                "heading_level": 0,
                "children": [],
                "content": ""
            }
            tree.append(node)
            stack.append((0, node))
            self._append_to_node_content(node, text)
            node["content"] = self._merge_ver_marker(node["content"])

    def _peek_heading_level(self, p_elem) -> Optional[int]:
        """Quick heading level detection from paragraph properties without full parse."""
        p_pr = p_elem.find(create_ns(W_NS, "pPr"))
        p_style = p_pr.find(create_ns(W_NS, "pStyle")) if p_pr is not None else None
        if p_style is not None:
            hlvl = self._style_to_heading_level.get(
                p_style.get(create_ns(W_NS, "val"), ""))
            if hlvl is not None:
                return hlvl
        outline = p_pr.find(create_ns(W_NS, "outlineLvl")) if p_pr is not None else None
        try:
            return int(outline.get(create_ns(W_NS, "val"), "")) + 1
        except (ValueError, TypeError, AttributeError):
            return None

    def _has_body_level_anchored_drawing(self, p_elem) -> bool:
        """Check if paragraph has an anchored drawing outside of text boxes."""
        for anc in p_elem.iter(create_ns(WP_NS, 'anchor')):
            if not self._is_anchor_inside_textbox(anc, p_elem):
                return True
        return False

    @staticmethod
    def _is_anchor_inside_textbox(elem, root_elem) -> bool:
        """Check if element is nested inside a txbxContent element."""
        parent = elem.getparent()
        while parent is not None and parent != root_elem:
            if parent.tag == create_ns(W_NS, "txbxContent"):
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _merge_ver_marker(text: str) -> str:
        """Remove a newline directly before the ▲Ver marker to keep text contiguous."""
        if not text:
            return text
        return text.replace("\n▲Ver", "▲Ver")\
                    .replace("(\n", "(")\
                    .replace("~~", "")\
                    .replace("~ ~", " ")

    @staticmethod
    def _normalize_text_for_matching(text: str) -> str:
        """
        Normalize text for matching between ToC entries and body headings.
        Removes numbering prefix, extra whitespace, and normalizes unicode.
        """
        if not text:
            return ""
        # Handles cases with or without space after numbering
        normalized = re.sub(r'^[\d.]+[\s\u3000]*', '', text)
        # Remove tabs and normalize whitespace
        normalized = re.sub(r'[\t\u3000]+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove page numbers at the end (ToC often has page numbers)
        normalized = re.sub(r'\d+$', '', normalized)
        return normalized.strip()

    @staticmethod
    def _append_non_newline(char: str, result: List[str], last_non_space: Optional[str]) -> Optional[str]:
        """Append a non-newline character to result, collapsing consecutive spaces.

        Returns the updated last_non_space tracker.
        """
        if char == " " and result and result[-1] == " ":
            return last_non_space
        result.append(char)
        return char if not char.isspace() else last_non_space

    @staticmethod
    def _flush_newline_separator(result: List[str], last_non_space: Optional[str]) -> Optional[str]:
        """Replace a newline with the appropriate sentence separator.

        Strips trailing whitespace from result, then injects ``" "`` when the
        last visible character was ``"."`` or ``". "`` otherwise.
        Returns the updated last_non_space tracker.
        """
        while result and result[-1].isspace():
            result.pop()
        if not last_non_space:
            return last_non_space

        replacement = " " if last_non_space == "." else ". "
        for repl_char in replacement:
            last_non_space = DocxParser._append_non_newline(repl_char, result, last_non_space)
        return last_non_space

    @staticmethod
    def _normalize_table_cell_text(cell_text: str) -> str:
        """Replace newlines inside a table cell following the requested rules."""
        if not cell_text:
            return ""

        result: List[str] = []
        last_non_space: Optional[str] = None

        for char in cell_text:
            if char == "\n":
                last_non_space = DocxParser._flush_newline_separator(result, last_non_space)
            else:
                last_non_space = DocxParser._append_non_newline(char, result, last_non_space)

        return "".join(result).strip()

    _TOC_STYLE_PATTERN = re.compile(r'^TOC(\d+)$', re.IGNORECASE)
    _TOC_NUMBERING_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)[\s\u3000]*(?=[^\d\s.]|$)')

    def _extract_toc_numbering_entry(self, full_text: str) -> None:
        """If full_text starts with a dotted numbering prefix, record it in the TOC map."""
        num_match = self._TOC_NUMBERING_PATTERN.match(full_text)
        if not num_match:
            return
        numbering = num_match.group(1).rstrip('.')
        text_without_num = full_text[num_match.end():].strip()
        normalized_text = self._normalize_text_for_matching(text_without_num)
        if normalized_text:
            self._toc_numbering_map[normalized_text] = numbering

    def _extract_toc_entries(self, root) -> None:
        """
        Extract Table of Contents entries to build numbering ground truth.
        ToC entries typically have styles like TOC1, TOC2, TOC3, etc.
        """
        self._toc_numbering_map = {}
        self._has_toc = False

        body = root.find(create_ns(W_NS, "body"))
        if body is None:
            return

        for p_elem in body.findall(create_ns(W_NS, "p")):
            ppr = p_elem.find(create_ns(W_NS, "pPr"))
            pstyle = ppr.find(create_ns(W_NS, "pStyle")) if ppr is not None else None
            if pstyle is None:
                continue

            style_val = pstyle.get(create_ns(W_NS, "val"), "")
            if not self._TOC_STYLE_PATTERN.match(style_val):
                continue

            self._has_toc = True

            full_text = self._get_paragraph_text(p_elem)
            if not full_text:
                continue

            self._extract_toc_numbering_entry(full_text)

    def _skip_leading_empty_content(self, children, start_idx: int) -> int:
        while start_idx < len(children):
            elem = children[start_idx]
            localname = etree.QName(elem).localname
            if (localname == "p" and self._get_paragraph_text(elem).strip()) or localname in ("tbl", "sdt"):
                break
            start_idx += 1
        return start_idx

    # ---------- _find_content_start_index constants & helpers ----------

    _FRONT_MATTER_KEYWORDS = (
        "revision history", "change history", "change log", "version history",
        "document history", "table of contents", "contents",
        "変更履歴", "改訂履歴", "目次",
        "revision", "toc",
    )

    def _is_toc_style(self, style_id: str) -> bool:
        """Check if a style ID corresponds to a Table of Contents style."""
        return bool(
            style_id
            and (self._TOC_STYLE_PATTERN.match(style_id) or style_id in self._style_to_toc)
        )

    @staticmethod
    def _get_paragraph_style_val(p_elem) -> tuple:
        """Return (pPr, style_val) for a paragraph, or (None, None) when pPr is absent."""
        ppr = p_elem.find(create_ns(W_NS, "pPr"))
        if ppr is None:
            return None, None
        pstyle = ppr.find(create_ns(W_NS, "pStyle"))
        style_val = pstyle.get(create_ns(W_NS, "val"), "") if pstyle is not None else ""
        return ppr, style_val

    @staticmethod
    def _is_sdt_toc(sdt_elem) -> bool:
        """Return True if a structured document tag represents a Table of Contents."""
        sdtpr = sdt_elem.find(create_ns(W_NS, "sdtPr"))
        doc_part_obj = sdtpr.find(create_ns(W_NS, "docPartObj")) if sdtpr is not None else None
        gallery = doc_part_obj.find(create_ns(W_NS, "docPartGallery")) if doc_part_obj is not None else None
        if gallery is None:
            return False
        val = (gallery.get(create_ns(W_NS, "val")) or "").lower()
        return "contents" in val or "toc" in val

    def _is_front_matter_heading(self, p_elem, ppr) -> bool:
        """Return True if p_elem is a heading whose text matches a front-matter keyword."""
        heading_level = self._detect_heading_level_from_ppr(ppr)
        if heading_level is None:
            return False
        text = self._get_paragraph_text(p_elem).lower()
        return any(kw in text for kw in self._FRONT_MATTER_KEYWORDS)

    # ---------- _find_content_start_index ----------

    def _classify_content_child(self, child, index: int, toc_end_index: int) -> str:
        """Classify a document body child for front-matter detection.

        Returns one of:
        - ``'toc'``           – element belongs to the Table of Contents
        - ``'front_matter'``  – element is a front-matter heading that can be marked
        - ``'content'``       – element is a real content heading (search should stop)
        - ``'skip'``          – element is irrelevant (non-paragraph, no pPr, etc.)
        """
        tag = etree.QName(child).localname

        if tag == "sdt":
            return "toc" if self._is_sdt_toc(child) else "skip"

        if tag != "p":
            return "skip"

        ppr, style_val = self._get_paragraph_style_val(child)
        if ppr is None:
            return "skip"

        if self._is_toc_style(style_val):
            return "toc"

        if self._is_front_matter_heading(child, ppr):
            return "front_matter" if self._can_mark_front_matter(index, toc_end_index) else "skip"

        return "content"

    def _find_content_start_index(self, children: List) -> int:
        """
        Find the index where main document content starts, skipping:
        1. Revision History / Change Log sections (typically before ToC)
        2. Table of Contents (ToC) - identified by w:sdt with docPartGallery or TOC styles

        This method uses a conservative approach:
        - Primary: XML structure detection (w:sdt with Table of Contents)
        - Secondary: Style-based detection (TOC1, TOC2, etc. styles or "toc X" style names)
        - Tertiary: Semantic detection for common front matter headings

        Returns the index of the first element after front matter, or 0 if no front matter detected.
        """
        toc_end_index = -1
        front_matter_end_index = -1

        for i, child in enumerate(children):
            signal = self._classify_content_child(child, i, toc_end_index)

            if signal == "toc":
                toc_end_index = i
            elif signal == "front_matter":
                front_matter_end_index = i
            elif signal == "content" and self._has_detected_front_matter(toc_end_index, front_matter_end_index):
                return self._start_after_front_matter(
                    children, toc_end_index, front_matter_end_index
                )

        if toc_end_index >= 0:
            return self._skip_leading_empty_content(children, toc_end_index + 1)

        return 0

    # Helper for finding the start index of main document
    @staticmethod
    def _can_mark_front_matter(index: int, toc_end_index: int) -> bool:
        """
        Decide whether a heading can still be treated as front matter.

        Parameters
        ----------
        index : int
            Current paragraph index.
        toc_end_index : int
            Last detected ToC index. -1 means no ToC detected yet.

        Returns
        -------
        bool
            True if the heading should be treated as front matter.
        """
        return toc_end_index >= 0 or index < 20

    @staticmethod
    def _has_detected_front_matter(toc_end_index: int, front_matter_end_index: int) -> bool:
        """
        Check whether any front matter or ToC has already been detected.

        Parameters
        ----------
        toc_end_index : int
            Last detected ToC index.
        front_matter_end_index : int
            Last detected front matter heading index.

        Returns
        -------
        bool
            True if front matter has been detected.
        """
        return toc_end_index >= 0 or front_matter_end_index >= 0


    def _start_after_front_matter(self, children: List, toc_end_index: int, front_matter_end_index: int) -> int:
        """
        Compute the first content index after detected front matter.

        Parameters
        ----------
        children : List
            Document child elements.
        toc_end_index : int
            Last detected ToC index.
        front_matter_end_index : int
            Last detected front matter heading index.

        Returns
        -------
        int
            First non-empty content index after front matter.
        """
        start_idx = max(toc_end_index, front_matter_end_index) + 1
        return self._skip_leading_empty_content(children, start_idx)

    @staticmethod
    def _get_paragraph_text(p_elem) -> str:
        """Quick helper to get raw text from a paragraph without side effects."""
        text_parts = []
        for r in p_elem.findall(f".//{create_ns(W_NS, 'r')}"):
            for t in r.findall(create_ns(W_NS, "t")):
                if t.text:
                    text_parts.append(t.text)
        return "".join(text_parts)

    # ---------- _parse_paragraph helper methods ----------

    @staticmethod
    def _para_is_inside_textbox(p_elem) -> bool:
        """Return True if this paragraph is nested inside a txbxContent (shape text box)."""
        parent = p_elem.getparent()
        while parent is not None:
            if parent.tag == create_ns(W_NS, "txbxContent"):
                return True
            parent = parent.getparent()
        return False

    def _detect_heading_level_from_ppr(self, ppr) -> Optional[int]:
        """Detect heading level from pPr: style lookup first, then outlineLvl fallback."""
        if ppr is None:
            return None
        heading_level = None
        pstyle = ppr.find(create_ns(W_NS, "pStyle"))
        if pstyle is not None:
            style_val = pstyle.get(create_ns(W_NS, "val"))
            if style_val and style_val in self._style_to_heading_level:
                heading_level = self._style_to_heading_level[style_val]
        # Fallback: outlineLvl is 0-based, so add 1
        if heading_level is None:
            outline_lvl = ppr.find(create_ns(W_NS, "outlineLvl"))
            val = outline_lvl.get(create_ns(W_NS, "val")) if outline_lvl is not None else None
            try:
                heading_level = int(val) + 1
            except (ValueError, TypeError):
                pass
        return heading_level

    @staticmethod
    def _detect_floating_image_anchor(p_elem) -> bool:
        """Return True if paragraph has an anchored (floating) drawing with raster image content outside a textbox.

        Anchors containing only shapes/groups (e.g. wpg:wgp diagrams) are excluded so
        their shape text is still extracted normally.
        """
        for _anchor in p_elem.findall(f".//{create_ns(WP_NS, 'anchor')}"):
            _par = _anchor.getparent()
            _inside_txbx = False
            while _par is not None and _par != p_elem:
                if _par.tag == create_ns(W_NS, "txbxContent"):
                    _inside_txbx = True
                    break
                _par = _par.getparent()
            if not _inside_txbx:
                _has_img = (
                    _anchor.find(f".//{create_ns(A_NS, 'blip')}") is not None
                    or _anchor.find(f".//{create_ns(PIC_NS, 'pic')}") is not None
                    or _anchor.find(f".//{create_ns(V_NS, 'imagedata')}") is not None
                )
                if _has_img:
                    return True
        return False

    def _detect_para_struck(self, ppr) -> bool:
        """Return True if the paragraph's style is registered as a strike style."""
        if ppr is None:
            return False
        pstyle = ppr.find(create_ns(W_NS, "pStyle"))
        if pstyle is not None:
            style_val = pstyle.get(create_ns(W_NS, "val"))
            if style_val and style_val in self._strike_style_ids:
                return True
        return False

    def _resolve_skip_images_for_para(self, skip_images: bool, para_has_image: bool, p_elem) -> bool:
        """Return True if image extraction should be suppressed (crossed-out figure detection)."""
        if not skip_images and para_has_image and self._paragraph_image_is_crossed_out(p_elem):
            return True
        return skip_images

    @staticmethod
    def _is_run_skipped_by_ancestry(r, p_elem, heading_level: Optional[int]) -> bool:
        """Return True if a run should be skipped due to txbxContent or del ancestry."""
        parent = r.getparent()
        while parent is not None and parent != p_elem:
            if parent.tag == create_ns(W_NS, "txbxContent"):
                return True
            if parent.tag == create_ns(W_NS, "del"):
                return True
            parent = parent.getparent()
        return False


    @staticmethod
    def _update_field_stack(r, field_stack: List[dict]) -> None:
        """Update the field tracking stack from fldChar and instrText elements in a run.

        Marks REF / STYLEREF fields for skipping since their cached results
        may be stale.
        """
        fld_char = r.find(create_ns(W_NS, "fldChar"))
        if fld_char is not None:
            fld_type = fld_char.get(create_ns(W_NS, "fldCharType")) or ""
            if fld_type == "begin":
                field_stack.append({"instr": "", "in_result": False, "skip": False})
            elif fld_type == "separate" and field_stack:
                field_stack[-1]["in_result"] = True
            elif fld_type == "end" and field_stack:
                field_stack.pop()
        instr_el = r.find(create_ns(W_NS, "instrText"))
        if instr_el is not None and instr_el.text and field_stack:
            field_stack[-1]["instr"] += instr_el.text
            instr = field_stack[-1]["instr"].strip()
            if instr.startswith(("REF ", "STYLEREF ")):
                field_stack[-1]["skip"] = True

    @staticmethod
    def _is_run_in_skipped_field(field_stack: List[dict]) -> bool:
        """Return True if the current run is inside the result region of a field marked for skipping."""
        return any(f["in_result"] and f["skip"] for f in field_stack)

    def _collect_run_texts(
        self,
        p_elem,
        heading_level: Optional[int],
        para_has_image: bool,
        para_has_floating_drawing: bool,
        para_struck: bool,
        skip_images: bool,
    ) -> List[str]:
        """Collect text from all eligible runs in a paragraph.

        Respects ancestry skip rules (txbxContent / del) and field-result skip rules
        (REF / STYLEREF cached values).
        """
        text_parts: List[str] = []
        field_stack: List[dict] = []

        for r in p_elem.findall(f".//{create_ns(W_NS, 'r')}"):
            if self._is_run_skipped_by_ancestry(r, p_elem, heading_level):
                continue

            self._update_field_stack(r, field_stack)
            if self._is_run_in_skipped_field(field_stack):
                continue

            skip_text = self._should_skip_run_text_as_invisible(r, p_elem)
            run_text = self._parse_run(
                r,
                paragraph_has_image=para_has_image or para_has_floating_drawing,
                paragraph_struck=para_struck,
                skip_text=skip_text,
                skip_images=skip_images,
            )
            if run_text:
                text_parts.append(run_text)

        return text_parts

    def _resolve_para_numpr(self, ppr) -> Tuple[Optional[str], Optional[str]]:
        """Resolve list numbering (numId, ilvl) from pPr with style-inheritance fallback.

        Priority 1: explicit w:numPr on the paragraph.
        Priority 2: w:numPr inherited from the paragraph style.
        """
        if ppr is None:
            return None, None

        # Priority 1: explicit numPr
        num_id, ilvl = self._extract_numpr_vals(ppr.find(create_ns(W_NS, "numPr")))

        # Priority 2: fill gaps from style's numPr
        if num_id is None or ilvl is None:
            style_num_id, style_ilvl = self._get_style_numpr(ppr)
            num_id = num_id or style_num_id
            ilvl = ilvl or style_ilvl

        return num_id, ilvl

    @staticmethod
    def _extract_numpr_vals(num_pr) -> Tuple[Optional[str], Optional[str]]:
        """Extract (numId, ilvl) string values from a w:numPr element."""
        if num_pr is None:
            return None, None
        num_id_el = num_pr.find(create_ns(W_NS, "numId"))
        ilvl_el = num_pr.find(create_ns(W_NS, "ilvl"))
        num_id = num_id_el.get(create_ns(W_NS, "val")) if num_id_el is not None else None
        ilvl = ilvl_el.get(create_ns(W_NS, "val")) if ilvl_el is not None else None
        return num_id, ilvl

    def _get_style_numpr(self, ppr) -> Tuple[Optional[str], Optional[str]]:
        """Get (numId, ilvl) inherited from the paragraph style, if any."""
        pstyle = ppr.find(create_ns(W_NS, "pStyle"))
        style_val = pstyle.get(create_ns(W_NS, "val"), "") if pstyle is not None else ""
        style_entry = self._style_to_numpr.get(style_val) if style_val else None
        if style_entry is None:
            return None, None
        return style_entry[0], str(style_entry[1])

    def _apply_numbering_to_text(
        self,
        full_text: str,
        num_id: Optional[str],
        ilvl: Optional[str],
        heading_level: Optional[int],
        skip_numbering: bool,
    ) -> str:
        """Prepend a resolved numbering marker to full_text when all conditions are met.

        For headings, bullet markers or unresolved placeholders (%N) are rejected and
        the numbering counter state is rolled back to avoid off-by-one errors on later headings.
        """
        if not (num_id and ilvl and self._numbering_helper and not skip_numbering):
            return full_text
        try:
            helper = self._numbering_helper
            abstract_id = helper.num_to_abstract.get(num_id)
            counters_ref = helper.abstract_counters[abstract_id] if abstract_id else helper.counters[num_id]
            snapshot = dict(counters_ref)

            marker = helper.get_marker(num_id, int(ilvl))
            if not marker:
                return full_text

            if heading_level and (marker.startswith('•') or '%' in marker):
                # Roll back numbering state so this paragraph doesn't affect later headings.
                counters_ref.clear()
                counters_ref.update(snapshot)
                return full_text

            return f"{marker} {full_text}" if full_text else str(marker)
        except Exception:
            return full_text

    @staticmethod
    def _apply_list_level_prefix(
        full_text: str,
        num_id: Optional[str],
        ilvl: Optional[str],
        heading_level: Optional[int],
    ) -> str:
        """Prefix nested list items with tabs based on Word ``ilvl``.

        Level 0 is left unchanged. Level 1 => ``\t``, level 2 => ``\t\t``, etc.
        Headings are excluded so heading text is not indented accidentally when a
        document style also carries numbering metadata.
        """
        if heading_level or not full_text or not num_id or ilvl is None:
            return full_text
        try:
            level = int(ilvl)
        except (TypeError, ValueError):
            return full_text
        if level <= 0:
            return full_text
        return ("\t" * level) + full_text

    @staticmethod
    def _finalize_heading_output(full_text: str, heading_level: Optional[int]) -> Tuple[Optional[int], Optional[str]]:
        """Return the final (heading_level, heading_text), demoting version-marker-only headings.

        Headings whose entire text is a struck-through version marker (e.g. "▲3.00", "-3.00")
        are demoted to regular content.
        """
        heading_text = full_text if heading_level else None
        if heading_level and heading_text:
            _ht = heading_text.strip()
            if re.match(r'^[▲▽△▼]?\s*-?\s*\d+\.\d+\s*$', _ht):
                heading_level = None
                heading_text = None
        return heading_level, heading_text

    def _parse_paragraph(
        self, p_elem, *, skip_numbering: bool = False, skip_images: bool = False
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """
        Parse a paragraph element.

        Args:
            p_elem: The paragraph XML element
            skip_numbering: If True, skip numbering marker generation to avoid
                           side effects on counter state. Use this when calling
                           from utility functions like _is_effectively_empty_paragraph.

        Returns: (text, heading_level, heading_text)
        """
        # Skip paragraphs inside txbxContent (diagram/shape text boxes).
        if self._para_is_inside_textbox(p_elem):
            return "", None, None

        ppr = p_elem.find(create_ns(W_NS, "pPr"))
        heading_level = self._detect_heading_level_from_ppr(ppr)

        para_has_image = self._paragraph_has_image(p_elem)

        # Only detect floating anchors when no inline image was found.
        # Anchors with only shapes/groups (e.g. wpg:wgp diagrams) are content-bearing;
        # only treat anchors with actual raster image data as floating-image overlays.
        para_has_floating_drawing = (False if para_has_image else self._detect_floating_image_anchor(p_elem))

        para_struck = self._detect_para_struck(ppr)

        # Crossed-out figure: a stroke-only overlay in front of the single image cancels it visually.
        _skip_images = self._resolve_skip_images_for_para(skip_images, para_has_image, p_elem)

        text_parts = self._collect_run_texts(
            p_elem, heading_level, para_has_image, para_has_floating_drawing,
            para_struck, _skip_images,
        )
        full_text = "".join(text_parts).strip()

        if heading_level is None and not full_text:
            return "", None, None

        num_id, ilvl = self._resolve_para_numpr(ppr)
        full_text = self._apply_numbering_to_text(full_text, num_id, ilvl, heading_level, skip_numbering)
        full_text = self._apply_list_level_prefix(full_text, num_id, ilvl, heading_level)

        heading_level, heading_text = self._finalize_heading_output(full_text, heading_level)

        return full_text, heading_level, heading_text

    def _paragraph_has_image(self, p_elem) -> bool:
        """
        True if this paragraph contains an actual image (a:blip / pic:pic / v:imagedata),
        excluding anything inside w:txbxContent.
        """
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False

        # Each entry: (xpath to find candidates, callable that returns True when elem has image)
        _has_vml_imagedata = lambda el: el.find(f".//{create_ns(V_NS, 'imagedata')}") is not None
        checks = [
            (create_ns(W_NS, "drawing"), self._drawing_contains_image),
            (create_ns(W_NS, "pict"),    _has_vml_imagedata),
            (create_ns(W_NS, "object"),  _has_vml_imagedata),
        ]

        for tag, has_image in checks:
            for elem in p_elem.findall(f".//{tag}"):
                if self._is_anchor_inside_textbox(elem, p_elem):
                    continue
                if has_image(elem):
                    return True

        return False

    @staticmethod
    def _collect_text_from_run_children(r_elem) -> List[str]:
        """Extract visible text tokens from a run's child elements."""
        _TAG_MAP = {
            "t": "text",
            "delText": "text",
            "tab": " ",
            "br": "\n",
            "noBreakHyphen": "-",
        }
        parts: List[str] = []
        for child in r_elem:
            action = _TAG_MAP.get(etree.QName(child).localname)
            if action == "text":
                if child.text:
                    parts.append(child.text)
            elif action is not None:
                parts.append(action)
        return parts

    def _parse_run(
        self,
        r_elem,
        *,
        paragraph_has_image: bool = False,
        paragraph_struck: bool = False,
        skip_text: bool = False,
        skip_images: bool = False,
    ) -> str:
        """Parse a run element and extract text, images, and shapes."""

        # detect run-level strike first
        run_struck = _elem_has_any_child(
            r_elem.find(create_ns(W_NS, "rPr")), W_NS, "strike", "dstrike"
        )
        struck = paragraph_struck or run_struck

        # If struck, drop EVERYTHING in this run (including images), so deprecated figures/captions won't leak images.
        if struck and not self.keep_strikethrough_text:
            return ""

        image_placeholders = [] if skip_images else self._extract_images_from_element(r_elem)
        shape_placeholders = [] if paragraph_has_image else self._extract_shapes_from_element(r_elem)

        # Extract visible text (suppress if "invisible": white-on-white / hidden).
        text_parts = [] if skip_text else self._collect_text_from_run_children(r_elem)

        # Still keep images and shapes
        text_parts.extend(image_placeholders)
        text_parts.extend(shape_placeholders)
        return "".join(text_parts)

    # ---------- Table merge helpers ----------

    def _is_pagebreak_only_paragraph(self, p_elem) -> bool:
        """True if paragraph contains a hard page break and no meaningful text."""
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False
        for br in p_elem.findall(f".//{create_ns(W_NS,'br')}"):
            if (br.get(create_ns(W_NS, "type")) or "").lower() == "page":
                txt, _, _ = self._parse_paragraph(p_elem, skip_numbering=True)
                return txt.strip() == ""
        return False

    def _is_effectively_empty_paragraph(self, p_elem) -> bool:
        """True if paragraph yields no extracted text (bookmarks-only / whitespace-only)."""
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False
        txt, _, _ = self._parse_paragraph(p_elem, skip_numbering=True)
        return txt.strip() == ""

    @staticmethod
    def _explicit_header_row_count(tbl_elem) -> int:
        """Count contiguous top rows marked as repeating headers via w:tblHeader."""
        if tbl_elem is None or tbl_elem.tag != create_ns(W_NS, "tbl"):
            return 0
        count = 0
        for tr in tbl_elem.findall(create_ns(W_NS, "tr")):
            trpr = tr.find(create_ns(W_NS, "trPr"))
            if trpr is not None and trpr.find(create_ns(W_NS, "tblHeader")) is not None:
                count += 1
                continue
            break
        return count

    def _table_has_explicit_header_rows(self, tbl_elem) -> bool:
        """Strong signal: table has w:trPr/w:tblHeader repeating header rows."""
        return self._explicit_header_row_count(tbl_elem) > 0

    @staticmethod
    def _tbllook_firstrow_enabled(tbl_elem) -> bool:
        """Best-effort: detect tblLook firstRow flag (attr or bitmask)."""
        tblpr = tbl_elem.find(create_ns(W_NS, "tblPr")) if tbl_elem is not None else None
        tl = tblpr.find(create_ns(W_NS, "tblLook")) if tblpr is not None else None

        # Newer docs: w:firstRow="1"
        first_row = tl.get(create_ns(W_NS, "firstRow")) or tl.get("firstRow") if tl is not None else None
        if first_row and str(first_row).lower() in {"1", "true", "on"}:
            return True

        # Older docs: bitmask in w:val; 0x0020 => firstRow
        val = tl.get(create_ns(W_NS, "val")) or tl.get("val") if tl is not None else None
        if not val:
            return False
        try:
            mask = int(str(val), 16)
            enabled = (mask & 0x0020) != 0
        except ValueError:
            enabled = False

        return enabled


    def _tbl_firstrow_cnf_hint(self, tbl_elem) -> bool:
        """Best-effort: detect cnfStyle firstRow on the first row/cell."""
        tr = tbl_elem.find(create_ns(W_NS, "tr")) if tbl_elem is not None else None
        if tr is None:
            return False
        tcs = tr.findall(create_ns(W_NS, "tc"))
        if not tcs:
            return False
        cnf = self._cnf_attrs(tcs[0], tr)
        return cnf.get("firstRow") in {"1", "true", "on"}


    @staticmethod
    def _normalize_sig_text(s: str) -> str:
        if not s:
            return ""
        s = re.sub(r"\[START_IMAGE_PATH\].*?\[END_IMAGE_PATH\]", "", s)
        s = s.replace("\u3000", " ")
        s = re.sub(r"\s+", " ", s)
        return s.strip().lower()


    def _header_signature(self, tbl_elem, grid_rows: List[List[str]]) -> str:
        """Header signature for merge decisions: explicit header rows else first row."""
        if not grid_rows:
            return ""
        n_hdr = self._explicit_header_row_count(tbl_elem)
        if n_hdr <= 0:
            n_hdr = 1
        parts = []
        for r in grid_rows[:n_hdr]:
            parts.append("||".join(self._normalize_sig_text(c) for c in r))
        return "\n".join(parts)


    def _scan_next_table_candidate(self, children, idx: int):
        """
        Find next table after idx, allowing only empty/pagebreak-only paragraphs as separators.

        Returns (next_tbl_idx, sep_indices) or (None, None).
        If a non-empty paragraph appears, chain stops.
        """
        j = idx + 1
        sep = []
        while j < len(children):
            node = children[j]
            if node.tag == create_ns(W_NS, "tbl"):
                return j, sep

            if node.tag != create_ns(W_NS, "p") \
                or not (self._is_effectively_empty_paragraph(node) or self._is_pagebreak_only_paragraph(node)):
                    return None, None
            sep.append(j)
            j += 1
        return None, None


    def _parse_table_chain(self, children, start_idx: int):
        """
        Parse a Case B/C table chain starting at start_idx.

        Returns (md_blocks, consumed_count).
        - Merge happens before markdown generation.
        - No XML modification: merge by concatenating grids.
        - Drop duplicated headers when signatures match.
        - Allow chaining across multiple split/adjacent tables.
        """
        assert children[start_idx].tag == create_ns(W_NS, "tbl")
        tbl0 = children[start_idx]
        cols0 = self._tbl_col_count(tbl0)

        group_rows = self._table_to_grid(tbl0)
        group_sig = self._header_signature(tbl0, group_rows)
        group_first_tbl = tbl0

        consumed_end = start_idx + 1

        while True:
            nxt_idx, _ = self._scan_next_table_candidate(children, consumed_end - 1)
            if nxt_idx is None:
                break
            nxt_tbl = children[nxt_idx]

            # Hard gate: columns must match
            if self._tbl_col_count(nxt_tbl) != cols0:
                break


            nxt_rows = self._table_to_grid(nxt_tbl)
            nxt_sig = self._header_signature(nxt_tbl, nxt_rows)

            # STRONG header only (tblHeader): treat as new table start only if explicit header differs
            nxt_has_exp_hdr = self._table_has_explicit_header_rows(nxt_tbl)
            if nxt_has_exp_hdr and group_sig and nxt_sig and nxt_sig != group_sig:
                break

            # Merge: consume separators and next table
            consumed_end = nxt_idx + 1

            # Drop duplicated headers ONLY when signatures match (safe)
            if group_sig and nxt_sig and nxt_sig == group_sig:
                n_drop = self._explicit_header_row_count(group_first_tbl)
                if n_drop <= 0:
                    n_drop = 1
                nxt_rows = nxt_rows[n_drop:]

            group_rows.extend(nxt_rows)

        md_blocks = []
        md = self._rows_to_markdown(group_rows)
        if md:
            md_blocks.append(md)

        return md_blocks, (consumed_end - start_idx), group_rows

    def _tbl_col_count(self, tbl_elem) -> int:
        """
        Determine table column count (grid width).
        Prefer w:tblGrid/w:gridCol. Fallback to inferred colspans if missing.
        """
        tbl_grid = tbl_elem.find(create_ns(W_NS, "tblGrid"))
        if tbl_grid is not None:
            cols = tbl_grid.findall(create_ns(W_NS, "gridCol"))
            if cols:
                return len(cols)

        # Fallback: infer from rows by summing gridSpans (best effort)
        max_cols = 0
        for tr in tbl_elem.findall(create_ns(W_NS, "tr")):
            cnt = self._row_grid_before(tr)
            for tc in tr.findall(create_ns(W_NS, "tc")):
                cnt += self._tc_grid_span(tc)
            max_cols = max(max_cols, cnt)
        return max_cols

    @staticmethod
    def _row_grid_before(tr_elem) -> int:
        """
        Row-level offset before first cell (w:trPr/w:gridBefore).
        Often absent; return 0 if not found.
        """
        trpr = tr_elem.find(create_ns(W_NS, "trPr"))
        gb = trpr.find(create_ns(W_NS, "gridBefore")) if trpr is not None else None
        if gb is None:
            return 0
        val = gb.get(create_ns(W_NS, "val"))
        try:
            return int(val) if val is not None else 0
        except ValueError:
            return 0

    @staticmethod
    def _tc_grid_span(tc_elem) -> int:
        """Cell horizontal span (w:tcPr/w:gridSpan/@w:val). Default 1."""
        tcpr = tc_elem.find(create_ns(W_NS, "tcPr"))
        gs = tcpr.find(create_ns(W_NS, "gridSpan")) if tcpr is not None else None
        if gs is None:
            return 1
        val = gs.get(create_ns(W_NS, "val"))
        try:
            return int(val) if val is not None else 1
        except ValueError:
            return 1

    @staticmethod
    def _tc_vmerge_state(tc_elem) -> str:
        """
        Vertical merge state:
        - "restart" if w:vMerge/@w:val="restart"
        - "continue" if w:vMerge exists with no val or val="continue"
        - "none" if no w:vMerge
        """
        tcpr = tc_elem.find(create_ns(W_NS, "tcPr"))
        vm = tcpr.find(create_ns(W_NS, "vMerge")) if tcpr is not None else None
        if vm is None:
            return "none"
        val = vm.get(create_ns(W_NS, "val"))
        if val is not None and str(val).lower() == "restart":
            return "restart"
        return "continue"

    def _tc_text(self, tc_elem) -> str:
        """Extract cell text and images (joins paragraphs). Uses _parse_paragraph().

        Note: Allow numbering extraction in table cells (skip_numbering=False) so that
        numbered list items like "1", "2", "3" in headers are preserved.
        Table cell numbering uses separate numId instances so it won't interfere
        with document-level heading numbering.
        """
        parts = []
        for p in tc_elem.findall(create_ns(W_NS, "p")):
            txt, _, _ = self._parse_paragraph(p, skip_numbering=False)
            if txt:
                parts.append(txt)
        return "\n".join(parts).strip()

    @staticmethod
    def _is_gray_hex(fill_hex: str, *, brightness_thr: float, spread_thr: int) -> bool:
        if not fill_hex or not re.fullmatch(HEX6_RE, fill_hex):
            return False
        fill_hex = fill_hex.upper()
        r = int(fill_hex[0:2], 16)
        g = int(fill_hex[2:4], 16)
        b = int(fill_hex[4:6], 16)
        spread = max(r, g, b) - min(r, g, b)
        brightness = (r + g + b) / 3.0
        return (spread <= spread_thr) and (brightness <= brightness_thr)

    @staticmethod
    def _has_revision_delete_attr(elem) -> bool:
        if elem is None:
            return False
        for key, value in (elem.attrib or {}).items():
            try:
                local_name = etree.QName(key).localname
            except Exception:
                local_name = str(key)
            if local_name == "rsidDel" and str(value).strip():
                return True
        return False

    def _has_revision_delete_marker(self, elem) -> bool:
        if elem is None:
            return False
        for node in elem.iter():
            try:
                qname = etree.QName(node)
            except Exception:
                continue
            if (
                qname.namespace == W_NS
                and qname.localname in self._REVISION_DELETE_LOCALNAMES
            ):
                return True
        return False

    def _resolve_scheme_color_hex(self, scheme_val: str) -> str:
        if not scheme_val or not self._theme_resolver:
            return ""
        normalized = str(scheme_val).strip()
        if not normalized:
            return ""
        alias = {
            "tx1": "dk1",
            "tx2": "dk2",
            "bg1": "lt1",
            "bg2": "lt2",
        }
        key = alias.get(normalized, normalized)
        return (self._theme_resolver.scheme_rgb.get(key, "") or "").upper()

    @staticmethod
    def _node_text_content(elem) -> str:
        if elem is None:
            return ""
        text_nodes = (
            elem.findall(f".//{create_ns(W_NS, 't')}")
            + elem.findall(f".//{create_ns(W_NS, 'delText')}")
            + elem.findall(f".//{create_ns(A_NS, 't')}")
        )
        chunks: List[str] = []
        for node in text_nodes:
            value = (node.text or "").strip()
            if value:
                chunks.append(value)
        return " ".join(chunks).strip()

    @classmethod
    def _node_has_visible_text(cls, elem) -> bool:
        return bool(cls._node_text_content(elem))

    @classmethod
    def _node_has_delete_overlay_text(cls, elem) -> bool:
        text = cls._node_text_content(elem)
        if not text:
            return False

        upper_text = text.upper()
        return any(
            (token.isascii() and token in upper_text)
            or (not token.isascii() and token in text)
            for token in cls._DELETE_OVERLAY_TEXT_PATTERNS
        )

    @staticmethod
    def _iter_vml_shapes(elem) -> List:
        if elem is None:
            return []
        shapes: List = []
        try:
            qname = etree.QName(elem)
            if qname.namespace == V_NS and qname.localname in {"shape", "rect", "oval"}:
                shapes.append(elem)
        except Exception:
            pass
        for tag_name in ("shape", "rect", "oval"):
            shapes.extend(elem.findall(f".//{create_ns(V_NS, tag_name)}"))
        return shapes

    @staticmethod
    def _safe_int(value: Optional[str], default: int = 0) -> int:
        try:
            return int(str(value))
        except Exception:
            return default

    @staticmethod
    def _clamp_u8(value: float) -> int:
        return max(0, min(255, int(round(value))))

    @staticmethod
    def _ooxml_ratio(value: Optional[str], default: int = 0, *, clamp_upper: bool = True) -> float:
        """Convert an OOXML 0..100000-style value to a non-negative ratio."""
        ratio = DocxParser._safe_int(value, default) / 100000.0
        if ratio < 0.0:
            return 0.0
        if clamp_upper and ratio > 1.0:
            return 1.0
        return ratio

    @staticmethod
    def _hex_to_rgb(fill_hex: str) -> Tuple[int, int, int]:
        normalized = fill_hex.strip().upper()
        return (
            int(normalized[0:2], 16),
            int(normalized[2:4], 16),
            int(normalized[4:6], 16),
        )

    @staticmethod
    def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"{r:02X}{g:02X}{b:02X}"


    # ---------- Invisible (white-on-white) text suppression helpers ----------
    @staticmethod
    def _hex6_to_rgb_u8(hex6: str) -> Optional[Tuple[int, int, int]]:
        if not hex6:
            return None
        h = str(hex6).strip().upper()
        if not re.fullmatch(HEX6_UPPER_RE, h):
            return None
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _is_near_white_hex(self, hex6: str) -> bool:
        """
        Treat [#FFFFFF .. ~98% white] as invisible (default cutoff = 0.98).
        0.98 * 255 ≈ 250 => channels >= 250 are considered near-white.
        """
        rgb = self._hex6_to_rgb_u8(hex6)
        if not rgb:
            return False
        thr = int(round(255 * float(getattr(self, "white_text_ratio_cutoff", 0.98))))
        r, g, b = rgb
        return (r >= thr and g >= thr and b >= thr)

    @staticmethod
    def _extract_color_hex_from_rpr(rpr) -> str:
        """Return a validated uppercase 6-hex color from an rPr element, or empty string."""
        c = rpr.find(create_ns(W_NS, "color")) if rpr is not None else None
        if c is None:
            return ""
        v = (c.get(create_ns(W_NS, "val")) or "").strip().upper()
        if v and v != "AUTO" and re.fullmatch(HEX6_UPPER_RE, v):
            return v
        return ""

    @staticmethod
    def _get_effective_run_color_hex(r_elem, p_elem) -> str:
        """
        Best-effort: get color from run rPr first, then paragraph pPr/rPr.
        Only uses w:color/@w:val (ignores themeColor for now).
        """
        # Run color
        run_color = DocxParser._extract_color_hex_from_rpr(
            r_elem.find(create_ns(W_NS, "rPr"))
        )
        if run_color:
            return run_color

        # Paragraph default color (pPr/rPr/color)
        ppr = p_elem.find(create_ns(W_NS, "pPr")) if p_elem is not None else None
        if ppr is not None:
            return DocxParser._extract_color_hex_from_rpr(
                ppr.find(create_ns(W_NS, "rPr"))
            )

        return ""

    def _run_has_highlight_or_shading(self, r_elem, p_elem) -> bool:
        """
        Return True if run/paragraph has highlight or shading fill that is NOT near-white,
        so white text could actually be visible.
        """
        def has_visible_fill(shd_elem) -> bool:
            """Return True when a <w:shd> element has a valid fill color that is neither auto/none nor near-white."""
            if shd_elem is None:
                return False

            fill = (shd_elem.get(create_ns(W_NS, "fill")) or shd_elem.get("fill") or "").strip().upper()

            return (
                bool(fill)
                and fill not in ("AUTO", "NONE")
                and re.fullmatch(HEX6_UPPER_RE, fill) is not None
                and not self._is_near_white_hex(fill)
            )

        run_highlight = False
        run_shading = False
        para_shading = False

        rpr = r_elem.find(create_ns(W_NS, "rPr"))
        if rpr is not None:
            hl = rpr.find(create_ns(W_NS, "highlight"))
            hv = ((hl.get(create_ns(W_NS, "val")) or "").strip().lower()) if hl is not None else ""
            run_highlight = bool(hv) and hv not in ("none", "nohighlight")

            shd = rpr.find(create_ns(W_NS, "shd"))
            run_shading = has_visible_fill(shd)

        ppr = p_elem.find(create_ns(W_NS, "pPr")) if p_elem is not None else None
        if ppr is not None:
            pshd = ppr.find(create_ns(W_NS, "shd"))
            para_shading = has_visible_fill(pshd)

        return run_highlight or run_shading or para_shading

    def _should_skip_run_text_as_invisible(self, r_elem, p_elem) -> bool:
        """
        True if:
        - run is hidden (vanish/webHidden), OR
        - near-white font color AND no non-white highlight/shading
        """
        rpr = r_elem.find(create_ns(W_NS, "rPr"))
        if _elem_has_any_child(rpr, W_NS, "vanish", "webHidden"):
            return True
        color_hex = self._get_effective_run_color_hex(r_elem, p_elem)
        if color_hex and self._is_near_white_hex(color_hex) and not self._run_has_highlight_or_shading(r_elem, p_elem):
            return True
        return False

    def _apply_drawing_color_transforms(self, base_hex: str, color_node) -> str:
        if not base_hex or color_node is None:
            return base_hex
        if not re.fullmatch(HEX6_RE, base_hex):
            return ""

        r, g, b = self._hex_to_rgb(base_hex)

        shade = color_node.find(create_ns(A_NS, "shade"))
        if shade is not None:
            shade_ratio = max(0.0, min(1.0, self._safe_int(shade.get("val"), 100000) / 100000.0))
            r = self._clamp_u8(r * shade_ratio)
            g = self._clamp_u8(g * shade_ratio)
            b = self._clamp_u8(b * shade_ratio)

        tint = color_node.find(create_ns(A_NS, "tint"))
        if tint is not None:
            tint_ratio = max(0.0, min(1.0, self._safe_int(tint.get("val"), 0) / 100000.0))
            r = self._clamp_u8(r + (255 - r) * tint_ratio)
            g = self._clamp_u8(g + (255 - g) * tint_ratio)
            b = self._clamp_u8(b + (255 - b) * tint_ratio)

        lum_mod = color_node.find(create_ns(A_NS, "lumMod"))
        lum_off = color_node.find(create_ns(A_NS, "lumOff"))

        if lum_mod is not None or lum_off is not None:
            mod_ratio = self._ooxml_ratio(
                lum_mod.get("val") if lum_mod is not None else "100000",
                100000,
                clamp_upper=False,
            )
            off_ratio = self._ooxml_ratio(
                lum_off.get("val") if lum_off is not None else "0",
                0,
            )
            r = self._clamp_u8(r * mod_ratio + 255 * off_ratio)
            g = self._clamp_u8(g * mod_ratio + 255 * off_ratio)
            b = self._clamp_u8(b * mod_ratio + 255 * off_ratio)


        return self._rgb_to_hex((r, g, b))

    _PRESET_COLOR_MAP = {
        "gray": "808080",
        "grey": "808080",
        "ltgray": "D3D3D3",
        "dkgray": "696969",
        "silver": "C0C0C0",
        "black": "000000",
        "white": "FFFFFF",
    }

    def _resolve_color_node_base_hex(self, node) -> str:
        """Return the base hex color for a single DrawingML color node, or empty string."""
        local = etree.QName(node).localname
        if local == "srgbClr":
            v = (node.get("val") or "").strip().upper()
            return v if re.fullmatch(HEX6_UPPER_RE, v) else ""
        if local == "schemeClr":
            return self._resolve_scheme_color_hex(node.get("val") or "")
        if local == "sysClr":
            v = (node.get("lastClr") or node.get("val") or "").strip().upper()
            return v if re.fullmatch(HEX6_UPPER_RE, v) else ""
        if local == "prstClr":
            return self._PRESET_COLOR_MAP.get((node.get("val") or "").strip().lower(), "")
        return ""

    def _resolve_solid_fill_hex(self, solid_fill) -> str:
        if solid_fill is None:
            return ""

        for child in solid_fill:
            base = self._resolve_color_node_base_hex(child)
            if base:
                return self._apply_drawing_color_transforms(base, child)

        return ""

    def _solid_fill_has_low_alpha(self, solid_fill) -> bool:
        if solid_fill is None:
            return False
        for tag_name in ("srgbClr", "schemeClr", "sysClr", "prstClr", "scrgbClr"):
            color_node = solid_fill.find(create_ns(A_NS, tag_name))
            if color_node is None:
                continue
            alpha = color_node.find(create_ns(A_NS, "alpha"))
            if alpha is None:
                continue
            if self._safe_int(alpha.get("val"), 100000) < 80000:
                return True
        return False

    @staticmethod
    def _extract_vml_style_value(style: str, keys: Tuple[str, ...]) -> str:
        if not style:
            return ""
        for key in keys:
            pattern = re.compile(rf"{re.escape(key)}\s*:\s*([^;]+)", re.IGNORECASE)
            match = pattern.search(style)
            if match:
                return (match.group(1) or "").strip()
        return ""

    @classmethod
    def _vml_shape_looks_translucent(cls, vshape) -> bool:
        if vshape is None:
            return False

        style = (vshape.get("style") or "").strip()
        opacity_raw = cls._extract_vml_style_value(style, ("opacity", "mso-opacity"))
        if not opacity_raw:
            return False

        value = opacity_raw.strip().lower()
        try:
            opacity = float(value[:-1]) / 100.0 if value.endswith("%") else float(value)
            if opacity > 1.0:
                opacity /= 100.0
        except Exception:
            opacity = None

        return opacity is not None and opacity < 0.8

    @staticmethod
    def _vml_shape_is_large_overlay(vshape) -> bool:
        if vshape is None:
            return False
        style = (vshape.get("style") or "").strip().lower()
        if "position:absolute" not in style:
            return False
        width_raw = DocxParser._extract_vml_style_value(style, ("width",))
        height_raw = DocxParser._extract_vml_style_value(style, ("height",))
        if not width_raw or not height_raw:
            return False

        def _to_points(value: str) -> Optional[float]:
            """Retrieve points value from a string e.g. '240pt' -> 240"""
            candidate = str(value or "").strip().lower()
            if candidate.endswith("pt"):
                candidate = candidate[:-2].strip()
            try:
                return float(candidate)
            except Exception:
                return None

        width_pt = _to_points(width_raw)
        height_pt = _to_points(height_raw)
        if width_pt is None or height_pt is None:
            return False
        return width_pt >= 250.0 and height_pt >= 120.0

    @staticmethod
    def _parse_pt_to_emu(value: str) -> int:
        """Parse a VML style dimension (e.g. '439.5pt') and return EMU."""
        v = (value or "").strip().lower()
        if not v:
            return 0
        if v.endswith("pt"):
            v = v[:-2].strip()
        try:
            return int(float(v) * 12700)
        except (ValueError, TypeError):
            return 0

    def _solid_fill_is_gray_overlay(self, solid_fill) -> bool:
        """Return True if a DrawingML solidFill qualifies as a gray overlay."""
        fill_hex = self._resolve_solid_fill_hex(solid_fill)
        if self._is_gray_hex(
            fill_hex,
            brightness_thr=self.gray_brightness_thr,
            spread_thr=self.gray_spread_thr,
        ):
            return True
        # Semi-transparent overlays are often used as delete masks.
        return (
            self._solid_fill_has_low_alpha(solid_fill)
            and (not fill_hex or self._is_gray_hex(fill_hex, brightness_thr=245.0, spread_thr=55))
        )

    _VML_NAMED_GRAYS = frozenset({"gray", "grey", "silver"})

    @classmethod
    def _resolve_vml_fill_hex(cls, vshape) -> str:
        """Best-effort: resolve a VML shape's fill color to a 6-hex string (uppercase), or ''."""
        color_raw = (vshape.get("fillcolor") or "").strip().lower()
        if not color_raw:
            style = (vshape.get("style") or "").strip()
            color_raw = cls._extract_vml_style_value(style, ("fillcolor", "mso-fill-color")).lower()
        if not color_raw:
            return ""
        if color_raw in cls._VML_NAMED_GRAYS:
            return {"gray": "808080", "grey": "808080", "silver": "C0C0C0"}[color_raw]
        m = re.search(f"({HEX6_RE})", color_raw)
        return m.group(1).upper() if m else ""

    def _vml_shape_has_gray_fill(self, vshape) -> bool:
        """Return True if a VML shape has a gray or translucent fill qualifying as an overlay."""
        fill_hex = self._resolve_vml_fill_hex(vshape)
        if not fill_hex:
            return self._vml_shape_looks_translucent(vshape)
        if self._is_gray_hex(
            fill_hex,
            brightness_thr=self.gray_brightness_thr,
            spread_thr=self.gray_spread_thr,
        ):
            return True
        return (
            self._vml_shape_looks_translucent(vshape)
            and self._is_gray_hex(fill_hex, brightness_thr=245.0, spread_thr=55)
        )

    def _node_has_gray_overlay_fill(self, elem) -> bool:
        if elem is None:
            return False

        # DrawingML shapes.
        for solid_fill in elem.findall(f".//{create_ns(A_NS, 'solidFill')}"):
            if self._solid_fill_is_gray_overlay(solid_fill):
                return True

        # VML fallback shapes.
        for vshape in self._iter_vml_shapes(elem):
            if self._vml_shape_has_gray_fill(vshape):
                return True

        return False

    def _drawing_is_opaque_front_overlay(self, drawing_elem) -> bool:
        """Return True when a DrawingML drawing is a large opaque front overlay."""
        anchor = self._get_front_anchor(drawing_elem)
        if anchor is None:
            return False

        if not self._anchor_is_large_enough(anchor, min_width_pt=250.0, min_height_pt=80.0):
            return False

        return self._anchor_has_opaque_shape_fill(anchor)

    @staticmethod
    def _get_front_anchor(drawing_elem):
        """
        Return the wp:anchor element only if the drawing is anchored in front
        of document content. Otherwise return None.

        Parameters
        ----------
        drawing_elem : lxml element
            The DrawingML drawing element.

        Returns
        -------
        lxml element | None
            The wp:anchor element if present and in front of content, else None.
        """
        if drawing_elem is None:
            return None

        anchor = drawing_elem.find(create_ns(WP_NS, "anchor"))
        if anchor is None or anchor.get("behindDoc") == "1":
            return None

        return anchor

    @staticmethod
    def _anchor_is_large_enough(anchor, min_width_pt: float, min_height_pt: float) -> bool:
        """
        Check whether a wp:anchor has extent large enough in points.

        Parameters
        ----------
        anchor : lxml element
            The wp:anchor element.

        min_width_pt : float
            Minimum required width in points.

        min_height_pt : float
            Minimum required height in points.

        Formula
        -------
        width_pt = cx / 12700
        height_pt = cy / 12700

        Where:
        - cx: width in EMU (English Metric Units)
        - cy: height in EMU
        - 12700: number of EMUs in 1 point
        """
        extent = anchor.find(create_ns(WP_NS, "extent"))
        if extent is None:
            return False

        try:
            cx = int(extent.get("cx", "0"))
            cy = int(extent.get("cy", "0"))
        except (ValueError, TypeError):
            return False

        width_pt = cx / 12700.0
        height_pt = cy / 12700.0

        return width_pt >= min_width_pt and height_pt >= min_height_pt

    def _sppr_is_visually_opaque(self, sp_pr) -> bool:
        if sp_pr.find(create_ns(A_NS, "noFill")) is not None:
            return False

        solid = sp_pr.find(create_ns(A_NS, "solidFill"))
        if solid is not None:
            is_opaque = not self._solid_fill_has_low_alpha(solid)
        else:
            wsp = sp_pr.getparent()
            style_el = wsp.find(create_ns(WPS_NS, "style")) if wsp is not None else None
            fill_ref = style_el.find(create_ns(A_NS, "fillRef")) if style_el is not None else None

            if fill_ref is None:
                is_opaque = False
            else:
                try:
                    is_opaque = int(fill_ref.get("idx", "0")) > 0
                except (ValueError, TypeError):
                    is_opaque = False

        return is_opaque

    @staticmethod
    def _iter_anchor_shape_properties(anchor):
        """
        Yield all shape property elements (wps:spPr) under the given anchor.
        """
        yield from anchor.findall(f".//{create_ns(WPS_NS, 'spPr')}")

    def _anchor_has_opaque_shape_fill(self, anchor) -> bool:
        return any(
            self._sppr_is_visually_opaque(sp_pr)
            for sp_pr in self._iter_anchor_shape_properties(anchor)
        )

    def _paragraph_has_opaque_front_overlay(self, p_elem) -> bool:
        """Return True when a body-level paragraph contains at least one large
        opaque front-anchored shape that acts as a visual curtain hiding
        content beneath it.

        Used to detect page-covering overlay rectangles placed in body
        paragraphs (as opposed to table cells which are handled separately).
        """
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False
        for drawing in p_elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if self._drawing_is_opaque_front_overlay(drawing):
                return True
        return False

    def _shape_is_delete_overlay(self, elem) -> bool:
        is_overlay = False

        if elem is not None and self._node_has_gray_overlay_fill(elem):
            if self._node_has_delete_overlay_text(elem) or not self._node_has_visible_text(elem):
                is_overlay = True
            else:
                for vshape in self._iter_vml_shapes(elem):
                    if self._vml_shape_is_large_overlay(vshape):
                        is_overlay = True
                        break

        return is_overlay

    @staticmethod
    def _drawing_contains_image(drawing) -> bool:
        return (
            drawing.find(f".//{create_ns(A_NS, 'blip')}") is not None
            or drawing.find(f".//{create_ns(PIC_NS, 'pic')}") is not None
            or drawing.find(f".//{create_ns(V_NS, 'imagedata')}") is not None
        )

    def _node_has_gray_overlay_shape(self, elem) -> bool:
        if elem is None:
            return False

        has_gray_overlay = False
        for drawing in elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if self._drawing_contains_image(drawing):
                continue

            if self._shape_is_delete_overlay(drawing) or self._drawing_is_opaque_front_overlay(drawing):
                has_gray_overlay = True
                break

        if not has_gray_overlay:
            for vshape in self._iter_vml_shapes(elem):
                if self._shape_is_delete_overlay(vshape):
                    has_gray_overlay = True
                    break

        return has_gray_overlay

    def _cell_has_gray_overlay_shape(self, tc_elem) -> bool:
        return self._node_has_gray_overlay_shape(tc_elem)

    def _table_has_gray_overlay_shape(self, tbl_elem) -> bool:
        return self._node_has_gray_overlay_shape(tbl_elem)

    @classmethod
    def _text_has_delete_overlay_marker(cls, text: str) -> bool:
        normalized = str(text or "")
        if not normalized:
            return False
        upper_text = normalized.upper()
        return any(
            (token.isascii() and token in upper_text)
            or (not token.isascii() and token in normalized)
            for token in cls._DELETE_OVERLAY_TEXT_PATTERNS
        )

    def _is_deleted_table_like_element(
        self,
        elem,
        prop_tag_localname: str | None = None,
        stop_at_tag_localname: str | None = None,
    ) -> bool:
        """
        Check whether a table-related element is deleted by tracked revisions.

        Parameters
        ----------
        elem : lxml element
            The XML element to inspect. Examples:
            - w:tbl for a table
            - w:tr for a table row
            - w:tc for a table cell

        prop_tag_localname : str | None
            The local tag name of the property child to inspect for revision-delete markers.
            Examples:
            - "tblPr" for table properties
            - "trPr" for row properties
            - "tcPr" for cell properties

            If None, no property child is searched.

        stop_at_tag_localname : str | None
            The local tag name of the ancestor at which upward traversal should stop.
            Examples:
            - None: do not stop early, walk to the root
            - "tbl": stop when a table ancestor is reached

            Important:
            - The stop happens before checking that ancestor itself, which preserves
            the same behavior as your original row/cell functions.
        """
        prop_elem = None
        if prop_tag_localname is not None and elem is not None:
            prop_elem = elem.find(create_ns(W_NS, prop_tag_localname))

        if self._has_revision_delete_attr(elem) or self._has_revision_delete_marker(prop_elem):
            return True

        stop_tag = create_ns(W_NS, stop_at_tag_localname) if stop_at_tag_localname else None

        parent = elem
        while parent is not None and (stop_tag is None or parent.tag != stop_tag):
            try:
                qname = etree.QName(parent)
            except Exception:
                parent = parent.getparent()
                continue

            if qname.namespace == W_NS and qname.localname in self._REVISION_DELETE_LOCALNAMES:
                return True

            parent = parent.getparent()

        return False

    def _is_deleted_table(self, tbl_elem) -> bool:
        return self._is_deleted_table_like_element(
            elem=tbl_elem,
            prop_tag_localname="tblPr",
            stop_at_tag_localname=None,
        )

    def _is_deleted_table_row(self, tr_elem) -> bool:
        return self._is_deleted_table_like_element(
            elem=tr_elem,
            prop_tag_localname="trPr",
            stop_at_tag_localname="tbl",
        )

    def _is_deleted_table_cell(self, tc_elem) -> bool:
        return self._is_deleted_table_like_element(
            elem=tc_elem,
            prop_tag_localname="tcPr",
            stop_at_tag_localname="tbl",
        )

    def _is_header_cell(self, r_idx: int, tbl_elem, tr_elem, tc_elem, spec: FillSpec) -> bool:
        """
        Decide whether this cell belongs to the table header row.
        Conservative: header if first row index OR cnfStyle firstRow flag OR style firstRow source.
        """
        is_header = False
        # Check multiple conditions - return True on first match
        # 0) Explicit repeating header rows: w:trPr/w:tblHeader
        try:
            if r_idx < self._explicit_header_row_count(tbl_elem):
                return True
        except Exception:
            pass

        # 1) First physical row
        if r_idx == 0:
            is_header = True

        # 2) cnfStyle firstRow flag from tcPr/trPr
        cnf = self._cnf_attrs(tc_elem, tr_elem)
        if cnf.get("firstRow") in {"1", "true", "on"}:
            is_header = True

        # 3) Style-driven firstRow conditional
        if spec and isinstance(spec.source, str) and spec.source.endswith(":firstRow"):
            is_header = True
        return is_header

    @staticmethod
    def _tbl_style_id(tbl_elem) -> str:
        tblpr = tbl_elem.find(create_ns(W_NS, "tblPr"))
        st = tblpr.find(create_ns(W_NS, "tblStyle")) if tblpr is not None else None
        if st is None:
            return ""
        return (st.get(create_ns(W_NS, "val")) or st.get("val") or "").strip()

    @staticmethod
    def _cnf_attrs(tc_elem, tr_elem) -> Dict[str, str]:
        """
        Extract cnfStyle attributes into a dict {localname: value}.
        We'll try cell cnfStyle first, then row cnfStyle.
        """
        def read_cnf(node, pr_tag: str) -> Dict[str, str]:
            """Read cnfStyle attributes from a node."""
            pr = node.find(create_ns(W_NS, pr_tag)) if node is not None else None
            cnf = pr.find(create_ns(W_NS, "cnfStyle")) if pr is not None else None
            if cnf is None:
                return {}
            out = {}
            for k, v in cnf.attrib.items():
                out[etree.QName(k).localname] = v
            return out

        return read_cnf(tc_elem, "tcPr") or read_cnf(tr_elem, "trPr")

    @staticmethod
    def _shd_to_spec(shd_el, source: str) -> FillSpec:
        if shd_el is None:
            return FillSpec()
        fill = (shd_el.get(create_ns(W_NS, "fill")) or shd_el.get("fill") or "").strip().upper()
        theme_fill = (shd_el.get(create_ns(W_NS, "themeFill")) or shd_el.get("themeFill") or "").strip()
        theme_shade = (shd_el.get(create_ns(W_NS, "themeFillShade")) or shd_el.get("themeFillShade") or "").strip()
        theme_tint = (shd_el.get(create_ns(W_NS, "themeFillTint")) or shd_el.get("themeFillTint") or "").strip()
        if fill and not re.fullmatch(HEX6_UPPER_RE, fill):
            fill = ""
        return FillSpec(fill, theme_fill, theme_shade, theme_tint, source)

    def _tc_shd_spec(self, tc_elem) -> FillSpec:
        tcpr = tc_elem.find(create_ns(W_NS, "tcPr"))
        if tcpr is None:
            return FillSpec()
        shd = tcpr.find(create_ns(W_NS, "shd"))
        return self._shd_to_spec(shd, source="tcPr")

    def _tr_shd_spec(self, tr_elem) -> FillSpec:
        trpr = tr_elem.find(create_ns(W_NS, "trPr"))
        if trpr is None:
            return FillSpec()
        shd = trpr.find(create_ns(W_NS, "shd"))
        return self._shd_to_spec(shd, source="trPr")

    def _effective_fill_spec(self, tbl_elem, tr_elem, tc_elem) -> FillSpec:
        """
        Priority:
        1) tcPr shading
        2) trPr shading
        3) table style shading (conditional via cnfStyle)
        """
        spec = self._tc_shd_spec(tc_elem)
        has_fill = spec.fill_hex or spec.theme_fill

        if not has_fill:
            spec = self._tr_shd_spec(tr_elem)
            has_fill = spec.fill_hex or spec.theme_fill

        if not has_fill:
            style_id = self._tbl_style_id(tbl_elem)
            if style_id and self._table_style_helper:
                cnf = self._cnf_attrs(tc_elem, tr_elem)
                spec = self._table_style_helper.resolve_spec(style_id, cnf)
                has_fill = spec.fill_hex or spec.theme_fill

        return spec if has_fill else FillSpec()

    def _cell_is_gray(self, tbl_elem, tr_elem, tc_elem) -> Tuple[bool, str, FillSpec]:
        """
        Returns: (is_gray, resolved_hex, spec_used)
        """
        spec = self._effective_fill_spec(tbl_elem, tr_elem, tc_elem)
        resolved = self._theme_resolver.resolve_to_hex(spec) if self._theme_resolver else (spec.fill_hex or "")
        is_gray = self._is_gray_hex(resolved, brightness_thr=self.gray_brightness_thr, spread_thr=self.gray_spread_thr)
        return is_gray, resolved, spec

    def _resolve_cell_gray_status(
        self, r_idx: int, tbl_elem, tr, tc,
    ) -> tuple:
        """
        Determine whether a table cell should be treated as gray (deleted/suppressed).

        Returns
        -------
        gray : bool
            Whether the cell content should be blanked out.
        gray_overlay_deleted : bool
            Whether the gray status comes from an overlay shape or text marker.
        spec : FillSpec
            The fill specification used for header-cell detection upstream.
        """
        cell_deleted_by_revision = (
            self.drop_deleted_table_content and self._is_deleted_table_cell(tc)
        )
        gray_overlay_deleted = False

        if cell_deleted_by_revision:
            gray = True
            spec = FillSpec(source="revision_delete")
        else:
            gray, _, spec = self._cell_is_gray(tbl_elem, tr, tc)
            if self.drop_deleted_table_content and self._cell_has_gray_overlay_shape(tc):
                gray = True
                gray_overlay_deleted = True

        # KEEP HEADER CONTENT only for normal header styling, not explicit delete marks.
        if (
            self._is_header_cell(r_idx, tbl_elem, tr, tc, spec)
            and not cell_deleted_by_revision
            and not gray_overlay_deleted
        ):
            gray = False

        return gray, gray_overlay_deleted, spec

    @staticmethod
    def _apply_vmerge_continue(
        col: int, end: int, gray: bool,
        row: list, vmerge: '_VmergeState', seen_continue: list,
    ) -> None:
        """
        Handle a vertical-merge continuation cell (vMerge without val="restart").

        Copies the text from the active vertical merge region into the current row,
        blanking it if the continuation cell is gray.
        """
        for k in range(col, end):
            vmerge.mask[k] = vmerge.mask[k] or gray
            seen_continue[k] = True
            row[k] = "" if vmerge.mask[k] else (vmerge.text[k] if vmerge.on[k] else "")

    def _apply_normal_cell(
        self, tc, col: int, end: int, gray: bool, vstate: str,
        row: list, vmerge: '_VmergeState',
    ) -> bool:
        """
        Handle a normal (non-continuation) table cell: extract text, write across
        colspan, and optionally start a new vertical merge region.

        Returns
        -------
        gray : bool
            Possibly updated gray flag (if overlay marker found in cell text).
        """
        raw_cell_text = self._tc_text(tc)

        # Check for delete-overlay marker inside cell text
        if (
            self.drop_deleted_table_content
            and SHAPE_CONTENT_START_MARKER in raw_cell_text
            and self._text_has_delete_overlay_marker(raw_cell_text)
        ):
            gray = True

        raw_text = self._normalize_table_cell_text(raw_cell_text)
        final_text = "" if gray else raw_text

        # Write across colspan, closing any previous active vertical merges
        for k in range(col, end):
            row[k] = final_text
            if vmerge.on[k]:
                vmerge.on[k] = False
                vmerge.text[k] = ""
                vmerge.mask[k] = False

        # Start a new vertical merge region if vstate is "restart"
        if vstate == "restart":
            for k in range(col, end):
                vmerge.on[k] = True
                vmerge.text[k] = final_text
                vmerge.mask[k] = gray
                vmerge.started_here[k] = True

        return gray

    @staticmethod
    def _fill_remaining_row_slots(
        col: int, row: list, vmerge: '_VmergeState', seen_continue: list,
    ) -> None:
        """
        Fill any remaining None slots in the row.

        Slots left as None were not covered by any <w:tc> in this row.
        If a vertical merge is active for that column, propagate its text;
        otherwise fill with empty string.
        """
        for c in range(col):
            if row[c] is None:
                if vmerge.on[c]:
                    row[c] = "" if vmerge.mask[c] else vmerge.text[c]
                    seen_continue[c] = True
                else:
                    row[c] = ""

    @staticmethod
    def _close_expired_rowspans(
        col: int, seen_continue: list,
        vmerge: '_VmergeState',
    ) -> None:
        """
        Close vertical merge regions that did not continue into this row.

        A region is kept alive if it was started here (``vmerge.started_here``)
        or a continuation cell was seen.  Otherwise the region is closed.
        """
        for c in range(col):
            if vmerge.started_here[c]:
                vmerge.on[c] = True
            elif vmerge.on[c] and not seen_continue[c]:
                vmerge.on[c] = False
                vmerge.text[c] = ""
                vmerge.mask[c] = False

    def _table_to_grid(self, tbl_elem) -> List[List[str]]:
        """
        Convert a <w:tbl> element into a rectangular grid (rows x cols) of cell texts.

        Core table parser used for Case B/C virtual table merging.
        NOTE: Does NOT modify the XML; only interprets structure (gridSpan + vMerge).
        """
        C = self._tbl_col_count(tbl_elem)
        if C <= 0:
            return []
        if self.drop_deleted_table_content and (
            self._is_deleted_table(tbl_elem) or self._table_has_gray_overlay_shape(tbl_elem)
        ):
            return []

        rows: List[List[str]] = []
        vmerge = _VmergeState(C)

        for r_idx, tr in enumerate(tbl_elem.findall(create_ns(W_NS, "tr"))):
            if self.drop_deleted_table_content and self._is_deleted_table_row(tr):
                continue

            row = self._process_table_row(r_idx, tbl_elem, tr, C, vmerge)

            # keep row if anything non-empty
            if any(str(cell).strip() for cell in row):
                rows.append([str(cell) for cell in row])

        return rows

    def _process_table_row(
        self, r_idx: int, tbl_elem, tr, C: int, vmerge: '_VmergeState',
    ) -> list:
        """Process a single <w:tr> and return a list of C cell-text values.

        Iterates over <w:tc> children, resolving gray status, gridSpan,
        and vMerge state for each cell.  After all cells are processed,
        fills remaining None slots and closes expired rowspans.

        Parameters
        ----------
        r_idx : int
            Zero-based row index (used for header detection).
        tbl_elem
            Parent <w:tbl> element.
        tr
            The <w:tr> element being processed.
        C : int
            Total column count.
        vmerge : _VmergeState
            Shared vertical-merge tracking state, mutated in place.
        """
        row = [None] * C
        seen_continue = [False] * C
        vmerge.begin_row()
        col = self._row_grid_before(tr)

        for tc in tr.findall(create_ns(W_NS, "tc")):
            colspan = self._tc_grid_span(tc)
            vstate = self._tc_vmerge_state(tc)

            if col >= C:
                break
            end = min(C, col + max(1, colspan))

            gray, _, _ = self._resolve_cell_gray_status(
                r_idx, tbl_elem, tr, tc,
            )

            if vstate == "continue":
                self._apply_vmerge_continue(
                    col, end, gray, row, vmerge, seen_continue,
                )
                col = end
                continue

            gray = self._apply_normal_cell(
                tc, col, end, gray, vstate,
                row, vmerge,
            )
            col = end

        self._fill_remaining_row_slots(C, row, vmerge, seen_continue)
        self._close_expired_rowspans(C, seen_continue, vmerge)

        return row


    def _rows_to_markdown(self, rows: List[List[str]]) -> str:
        """Convert table rows to Markdown format.

        Rejects single-row tables (no header/data distinction).
        First row is always treated as header.
        """
        # Reject:
        # - empty tables
        # - single-row tables: no meaningful header/data distinction
        # - column count is 0
        if not rows or len(rows) < 2:
            return ""
        max_cols = max(len(row) for row in rows) if rows else 0
        if max_cols == 0:
            return ""

        # Normalize rows
        normalized = []
        for row in rows:
            normalized.append(row + [""] * (max_cols - len(row)))

        # Build markdown
        md_lines = []
        for i, row in enumerate(normalized):
            # Escape pipe characters and replace newlines with <br> for multi-line cell content
            escaped = []
            for cell in row:
                cell_esc = self._normalize_table_cell_text(cell).replace("|", "\\|")
                pattern = rf"{re.escape(IMG_PATH_START_MARKER)}(.*?){re.escape(IMG_PATH_END_MARKER)}"
                cell_esc = re.sub(
                    pattern,
                    lambda m: f"{IMG_PATH_START_MARKER}" + m.group(1).replace("\\|", "|") + f"{IMG_PATH_END_MARKER}",
                    cell_esc,
                    flags=re.DOTALL
                )
                escaped.append(cell_esc)
            md_lines.append("| " + " | ".join(escaped) + " |")
            if i == 0:
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(md_lines)

    @staticmethod
    def _should_prune_node(node: dict) -> bool:
        """Decide whether a heading node should be removed from the output tree."""
        heading_text = node.get("heading_text")
        normalized = heading_text.strip() if isinstance(heading_text, str) else ""
        # Drop ▲x.xx version marker headings (artifacts in some templates).
        if normalized.startswith("▲"):
            try:
                float(normalized[1:])
            except (TypeError, ValueError):
                pass
            else:
                return True

        content_text = node.get("content")
        has_content = bool(content_text.strip()) if isinstance(content_text, str) else False
        has_children = bool(node.get("children"))
        if not has_content and not has_children:
            return True
        return False

    def _prune_tree(self, tree: List[dict]) -> List[dict]:
        """Prune empty/artifact nodes from the parsed heading tree."""
        pruned: List[dict] = []
        for node in tree:
            children = node.get("children") or []
            if children:
                node["children"] = self._prune_tree(children)
            else:
                node["children"] = []

            if self._should_prune_node(node):
                continue
            pruned.append(node)
        return pruned

    # ------ Image handling methods -----

    @staticmethod
    def _md5(data: bytes) -> str:
        """Compute MD5 hash of bytes."""
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def _which(*names: str) -> Optional[str]:
        """Find first available executable from names."""
        for n in names:
            p = shutil.which(n)
            if p:
                return p
        return None

    def _ensure_image_dir(self) -> str:
        """Create and return temporary directory for images."""
        if self._image_dir is None:
            self._image_dir = tempfile.mkdtemp(prefix="docx_images_")
        return self._image_dir

    def _save_image_bytes(
        self,
        image_bytes: bytes,
        ext: Optional[str],
        *,
        rel_id: str = "",
    ) -> Optional[Tuple[str, str]]:
        """Persist image bytes to a temp file and return (path, md5)."""
        if not image_bytes:
            return None

        directory = self._ensure_image_dir()
        extension = (ext or "png").lstrip(".") or "png"
        image_hash = self._md5(image_bytes)

        self._image_counter += 1
        filename = f"img_{self._image_counter}_{image_hash[:8]}.{extension}"

        path = os.path.join(directory, filename)
        try:
            Path(path).write_bytes(image_bytes)
        except Exception as exc:
            log.warning("Unable to write image %s: %s", rel_id, exc)
            return None
        self._saved_images.append(path)
        return path, image_hash


    # ------ Diagram cluster -> image pipeline ------
    @staticmethod
    def _is_standalone_diagram(p_elem, anchor_tag, inline_tag, wgp_tag, wsp_tag) -> bool:
        """Return True if the paragraph is a self-contained diagram (wpg group with ≥5 wsp shapes)."""
        for wrapper in chain(p_elem.iter(anchor_tag), p_elem.iter(inline_tag)):
            has_wgp = next(wrapper.iter(wgp_tag), None) is not None
            wsp_count = sum(1 for _ in islice(wrapper.iter(wsp_tag), 5))
            if has_wgp and wsp_count >= 5:
                return True
        return False

    @staticmethod
    def _has_any_drawing(p_elem, anchor_tag, inline_tag) -> bool:
        """Return True if the paragraph contains at least one anchor or inline drawing."""
        return (
            next(p_elem.iter(anchor_tag), None) is not None
            or next(p_elem.iter(inline_tag), None) is not None
        )

    def _group_diagram_paragraphs(self, paragraph_elements: List) -> List[List]:
        """Group paragraph elements into independent sub-diagram clusters.

        A standalone diagram (single wpg group with ≥5 shapes) gets its own group.
        Consecutive drawing paragraphs form a cluster.  ≥2 consecutive empty
        paragraphs act as a cluster boundary.
        """
        anchor_tag = create_ns(WP_NS, 'anchor')
        inline_tag = create_ns(WP_NS, 'inline')
        wgp_tag = create_ns(WPG_NS, 'wgp')
        wsp_tag = create_ns(WPS_NS, 'wsp')

        sub_groups: List[List] = []
        current_group: List = []
        pending_empties: List = []

        for p_elem in paragraph_elements:
            if self._is_standalone_diagram(p_elem, anchor_tag, inline_tag, wgp_tag, wsp_tag):
                if current_group:
                    sub_groups.append(current_group)
                    current_group = []
                pending_empties = []
                sub_groups.append([p_elem])
                continue

            if self._has_any_drawing(p_elem, anchor_tag, inline_tag):
                current_group.extend(pending_empties)
                pending_empties = []
                current_group.append(p_elem)
                continue

            # Non-drawing (empty) paragraph
            pending_empties.append(p_elem)
            if self._should_split_on_empty_gap(
                current_group,
                pending_empties,
                anchor_tag,
                inline_tag,
            ):
                sub_groups.append(current_group)
                current_group = []
                pending_empties = []

        if current_group:
            sub_groups.append(current_group)

        return sub_groups

    @staticmethod
    def _group_has_dense_anchor_paragraph(group: List, anchor_tag: str, inline_tag: str) -> bool:
        """Return True when any paragraph in group has many drawing holders.

        Dense anchor paragraphs are common in large sequence diagrams exported
        as many absolute-positioned shapes spread across multiple empty runs.
        """
        for p_elem in group:
            holder_count = sum(1 for _ in chain(p_elem.iter(anchor_tag), p_elem.iter(inline_tag)))
            if holder_count >= 10:
                return True
        return False

    def _should_split_on_empty_gap(
        self,
        current_group: List,
        pending_empties: List,
        anchor_tag: str,
        inline_tag: str,
    ) -> bool:
        """Return True if consecutive empty paragraphs should split the group."""
        if len(pending_empties) < 2 or not current_group:
            return False

        has_dense_anchor = self._group_has_dense_anchor_paragraph(
            current_group,
            anchor_tag,
            inline_tag,
        )
        # Keep dense anchor-heavy diagrams together through moderate spacer gaps.
        if has_dense_anchor and len(pending_empties) <= 12:
            return False

        return True

    def _diagram_cluster_to_images(
        self,
        paragraph_elements: List,
    ) -> List[str]:
        """Convert a cluster of drawing-only paragraphs into cropped diagram images.

        Pipeline:
          1. For each independent diagram found in the cluster, build a
             tiny 1-page DOCX containing only the relevant XML.
          2. Use ``soffice --headless`` to convert that DOCX to PDF.
          3. Render the PDF page(s) to PNG via ``pdftoppm`` (or fall back to
             ``soffice`` PNG export).
          4. Auto-crop white margins.
          5. Save the cropped PNG and return a list of
             ``[START_IMAGE_PATH] path|hash [END_IMAGE_PATH]`` placeholders.

        Anchored diagrams (``wp:anchor``) that live in a single paragraph
        are each rendered individually.  Non-anchored clusters (multiple
        paragraphs with anchored shapes that compose one visual diagram) are
        grouped and rendered together.

        Returns an empty list if conversion fails.
        """
        if not paragraph_elements:
            return []

        sub_groups = self._group_diagram_paragraphs(paragraph_elements)

        results: List[str] = []
        for group in sub_groups:
            placeholder = self._render_diagram_group_to_image(group)
            if placeholder:
                results.append(placeholder)

        return results

    def _render_diagram_group_to_image(
        self,
        paragraph_elements: List,
    ) -> Optional[str]:
        """Render a group of paragraph elements as a single diagram image.

        Builds a minimal DOCX, converts to PDF -> PNG, crops, and returns
        an ``[START_IMAGE_PATH] path|hash [END_IMAGE_PATH]`` placeholder
        or None on failure.
        """
        if not paragraph_elements:
            return None

        try:
            return self._render_diagram_group_to_image_impl(paragraph_elements)
        except Exception as exc:
            log.warning("Diagram-to-image conversion failed: %s", exc)
            return None

    def _render_diagram_group_to_image_impl(
        self,
        paragraph_elements: List,
    ) -> Optional[str]:
        docx_zip = self._docx_zip
        doc_xml = docx_zip.read(DOCX_DOC_XML)
        root = etree.fromstring(doc_xml)

        new_doc_bytes = self._build_mini_document_xml(root, paragraph_elements)
        blip_rids = self._collect_blip_rids(paragraph_elements)
        media_targets, new_rels_bytes = self._build_minimal_document_rels(docx_zip, blip_rids)
        new_ct_bytes = self._build_trimmed_content_types(docx_zip, media_targets)

        tmpdir, mini_docx_path = self._assemble_mini_docx(
            docx_zip=docx_zip,
            new_doc_bytes=new_doc_bytes,
            new_rels_bytes=new_rels_bytes,
            new_ct_bytes=new_ct_bytes,
            media_targets=media_targets,
        )

        try:
            pdf_path = self._convert_docx_to_pdf(mini_docx_path, tmpdir)
            if not pdf_path:
                return None

            png_path = self._convert_pdf_to_png(pdf_path, tmpdir)
            if not png_path:
                return None

            crop_mode, cropped = self._crop_rendered_image(png_path)
            if crop_mode == "error":
                return None

            final_path = self._save_rendered_image(png_path, cropped, crop_mode)
            image_hash = self._md5(Path(final_path).read_bytes())

            self._saved_images.append(final_path)
            return f"{IMG_PATH_START_MARKER} {final_path}|{image_hash} {IMG_PATH_END_MARKER}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


    def _build_mini_document_xml(self, root, paragraph_elements: List) -> bytes:
        """
        Build a minimal document.xml containing only the target paragraph elements,
        while preserving original section properties and shrinking margins.
        """
        W = W_NS

        new_root = deepcopy(root)
        new_body = new_root.find(f"{{{W}}}body")
        for child in list(new_body):
            new_body.remove(child)

        for p in paragraph_elements:
            new_body.append(deepcopy(p))

        body = root.find(f"{{{W}}}body")
        orig_sect = body.find(f"{{{W}}}sectPr") if body is not None else None
        if orig_sect is not None:
            new_sect = deepcopy(orig_sect)
            self._strip_header_footer_references(new_sect)
            self._shrink_section_margins(new_sect)
            new_body.append(new_sect)

        return etree.tostring(
            new_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )

    @staticmethod
    def _strip_header_footer_references(sect_pr) -> None:
        """
        Remove header/footer references from sectPr so the mini DOCX does not depend
        on header/footer parts that are not copied into the temporary package.
        """
        W = W_NS
        for tag in ("headerReference", "footerReference"):
            for el in sect_pr.findall(f"{{{W}}}{tag}"):
                sect_pr.remove(el)

    @staticmethod
    def _shrink_section_margins(sect_pr) -> None:
        """
        Reduce page margins to 0.1 inch to make the rendered diagram occupy more area.
        WordprocessingML margin unit here is twips:
            1 inch = 1440 twips
            0.1 inch = 144 twips
        """
        W = W_NS
        pg_mar = sect_pr.find(f"{{{W}}}pgMar")
        if pg_mar is None:
            return

        for attr in ("top", "right", "bottom", "left", "header", "footer"):
            pg_mar.set(f"{{{W}}}{attr}", "144")

    @staticmethod
    def _collect_blip_rids(paragraph_elements: List) -> set:
        """
        Collect rIds referenced by DrawingML a:blip elements inside the selected
        paragraphs. These usually point to embedded raster media used by grouped
        diagrams.
        """
        A = A_NS
        R = R_NS

        blip_rids = set()
        for p in paragraph_elements:
            for blip in p.iter(f"{{{A}}}blip"):
                rid = blip.get(f"{{{R}}}embed")
                if rid:
                    blip_rids.add(rid)
        return blip_rids

    @staticmethod
    def _build_minimal_document_rels(docx_zip, blip_rids: set) -> tuple[dict, bytes]:
        """
        Build a trimmed word/_rels/document.xml.rels that keeps:
        1. structural relationships needed by Word/LibreOffice
        2. media relationships referenced by collected blip rIds

        Returns:
            media_targets: dict[str, str]
                Mapping from relationship Id to target path, for example:
                    rId10 -> media/image10.png
            new_rels_bytes: bytes
                Serialized trimmed relationships XML
        """
        media_targets: dict = {}

        try:
            rels_xml = docx_zip.read(DOCX_RELS_DOCUMENT)
        except KeyError:
            return media_targets, b""

        rels_root = etree.fromstring(rels_xml)
        needed_targets = {
            "styles.xml",
            "settings.xml",
            "theme/theme1.xml",
            "fontTable.xml",
            "numbering.xml",
        }

        for rel in list(rels_root):
            target = rel.get("Target", "")
            rid = rel.get("Id", "")

            if target in needed_targets:
                continue

            if rid in blip_rids:
                media_targets[rid] = target
                continue

            rels_root.remove(rel)

        new_rels_bytes = etree.tostring(
            rels_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        return media_targets, new_rels_bytes

    @staticmethod
    def _build_trimmed_content_types(docx_zip, media_targets: dict) -> bytes:
        """
        Trim [Content_Types].xml so it only contains override parts needed by the
        mini DOCX and the media files referenced by kept blips.

        Variable legend:
            media_targets:
                dict mapping relationship Id to target path under word/, such as
                'rId10' -> 'media/image10.png'
            keep_parts:
                set of absolute OPC part names beginning with '/', such as
                '/word/document.xml' or '/word/media/image10.png'
        """
        try:
            ct_bytes = docx_zip.read(CONTENT_TYPES_XML)
        except KeyError:
            return b""

        ct_root = etree.fromstring(ct_bytes)
        ct_ns_uri = PKG_CT_NS

        keep_parts = {
            f"/{DOCX_DOC_XML}",
            f"/{DOCX_STYLES_XML}",
            f"/{DOCX_SETTINGS_XML}",
            f"/{DOCX_THEME1_XML}",
            f"/{DOCX_FONT_TABLE_XML}",
            f"/{DOCX_NUMBERING_XML}",
        }

        for target in media_targets.values():
            keep_parts.add(f"{WORD_PREFIX_SLASH}{target}")

        for override in list(ct_root.findall(f"{{{ct_ns_uri}}}Override")):
            if override.get("PartName", "") not in keep_parts:
                ct_root.remove(override)

        return etree.tostring(
            ct_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )


    def _assemble_mini_docx(
        self,
        docx_zip,
        new_doc_bytes: bytes,
        new_rels_bytes: bytes,
        new_ct_bytes: bytes,
        media_targets: dict,
    ) -> tuple[str, str]:
        """
        Assemble a temporary minimal DOCX package.

        Returns:
            tmpdir:
                Temporary working directory path.
            mini_docx_path:
                Path to the generated temporary DOCX file.
        """
        tmpdir = tempfile.mkdtemp(prefix="docx_diagram_")
        mini_docx_path = os.path.join(tmpdir, "diagram.docx")

        with zipfile.ZipFile(mini_docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
            if new_ct_bytes:
                zout.writestr(CONTENT_TYPES_XML, new_ct_bytes)

            top_rels = self._safe_zip_read(docx_zip, "_rels/.rels")
            if top_rels:
                zout.writestr("_rels/.rels", top_rels)

            zout.writestr(DOCX_DOC_XML, new_doc_bytes)

            if new_rels_bytes:
                zout.writestr(DOCX_RELS_DOCUMENT, new_rels_bytes)

            for extra in (
                DOCX_STYLES_XML,
                DOCX_SETTINGS_XML,
                DOCX_THEME1_XML,
                DOCX_FONT_TABLE_XML,
                DOCX_NUMBERING_XML,
            ):
                data = self._safe_zip_read(docx_zip, extra)
                if data:
                    zout.writestr(extra, data)

            for _rid, target in media_targets.items():
                media_path = f"{WORD_PREFIX}{target}"
                data = self._safe_zip_read(docx_zip, media_path)
                if data:
                    zout.writestr(media_path, data)

        return tmpdir, mini_docx_path

    @staticmethod
    def _safe_zip_read(docx_zip, path: str) -> Optional[bytes]:
        """
        Safely read a member from a zip archive.

        Variable legend:
            docx_zip:
                An opened zipfile.ZipFile for the DOCX package.
            path:
                Internal archive path, for example 'word/document.xml'.
        """
        try:
            return docx_zip.read(path)
        except KeyError:
            return None


    def _convert_docx_to_pdf(self, mini_docx_path: str, tmpdir: str) -> Optional[str]:
        """
        Convert the temporary DOCX into PDF using LibreOffice/soffice.

        Variable legend:
            mini_docx_path:
                Absolute filesystem path to the temporary DOCX.
            tmpdir:
                Output directory where the PDF should be written.
        """
        soffice = self._which("soffice", "libreoffice")
        if not soffice:
            log.warning("soffice/libreoffice not found – cannot render diagram")
            return None

        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmpdir, mini_docx_path],
            capture_output=True,
            text=True,
            timeout=60,
        )

        pdf_path = os.path.join(tmpdir, "diagram.pdf")
        if result.returncode != 0 or not os.path.exists(pdf_path):
            log.warning("soffice PDF conversion failed: %s", result.stderr)
            return None

        return pdf_path


    def _convert_pdf_to_png(self, pdf_path: str, tmpdir: str) -> Optional[str]:
        """
        Convert the first page of the rendered PDF into PNG.

        Strategy:
        1. Try pdftoppm at 300 DPI
        2. Fall back to soffice PNG export

        Variable legend:
            pdf_path:
                Absolute path to the rendered PDF.
            tmpdir:
                Working directory where PNG outputs are written.
        """
        pdftoppm = self._which("pdftoppm")
        if pdftoppm:
            prefix = os.path.join(tmpdir, "page")
            subprocess.run(
                [pdftoppm, "-png", "-r", "300", pdf_path, prefix],
                capture_output=True,
                timeout=30,
            )
            candidates = sorted(
                f for f in os.listdir(tmpdir)
                if f.startswith("page") and f.endswith(".png")
            )
            if candidates:
                return os.path.join(tmpdir, candidates[0])

        soffice = self._which("soffice", "libreoffice")
        if soffice:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "png", "--outdir", tmpdir, pdf_path],
                capture_output=True,
                timeout=30,
            )
            fallback = os.path.join(tmpdir, "diagram.png")
            if os.path.exists(fallback):
                return fallback

        log.warning("PDF-to-PNG conversion failed")
        return None

    @staticmethod
    def _crop_rendered_image(png_path: str):
        """
        Auto-crop near-white margins from the rendered PNG.

        Variable legend:
            img:
                PIL image opened from png_path.
            arr:
                NumPy array of shape (H, W, 3), where:
                    H = image height in pixels
                    W = image width in pixels
                    3 = RGB channels
            gray:
                Grayscale intensity matrix of shape (H, W), computed as channel mean.
            non_white:
                Boolean matrix of shape (H, W). A pixel is considered foreground when
                its grayscale intensity is strictly less than 250.
            rows_any:
                Boolean vector of length H. True means that row contains at least one
                non-white pixel.
            cols_any:
                Boolean vector of length W. True means that column contains at least one
                non-white pixel.
            r0, r1:
                Top and bottom crop bounds in pixel row coordinates.
            c0, c1:
                Left and right crop bounds in pixel column coordinates.
            margin:
                Extra padding in pixels added around the detected content box.
        """
        try:
            img = Image.open(png_path).convert("RGB")
            arr = np.array(img)
            gray = np.mean(arr, axis=2)
            non_white = gray < 250

            rows_any = np.any(non_white, axis=1)
            cols_any = np.any(non_white, axis=0)

            if not rows_any.any():
                log.warning("Rendered diagram image is all-white – skipping")
                return None

            r0 = int(np.argmax(rows_any))
            r1 = int(len(rows_any) - np.argmax(rows_any[::-1]))
            c0 = int(np.argmax(cols_any))
            c1 = int(len(cols_any) - np.argmax(cols_any[::-1]))

            margin = 20
            crop_box = (
                max(0, c0 - margin),
                max(0, r0 - margin),
                min(img.width, c1 + margin),
                min(img.height, r1 + margin),
            )
            return "cropped", img.crop(crop_box)

        except ImportError:
            log.warning("Pillow/numpy not available – returning uncropped image")
            return "original", None
        except Exception as exc:
            log.warning("Image crop failed: %s", exc)
            return "error", None


    def _save_rendered_image(self, png_path: str, cropped, crop_mode: str) -> str:
        directory = self._ensure_image_dir()
        self._image_counter += 1

        final_name = (
            f"img_{self._image_counter}_"
            f"{hashlib.md5(Path(png_path).read_bytes()).hexdigest()[:8]}.png"
        )
        final_path = os.path.join(directory, final_name)

        if crop_mode == "cropped":
            cropped.save(final_path)
        elif crop_mode == "original":
            shutil.copy2(png_path, final_path)
        else:
            raise ValueError(f"Unsupported crop_mode: {crop_mode}")

        return final_path

    @staticmethod
    def _try_run_converter(cmd: List[str], timeout: int, out_candidates: List[str]) -> Optional[bytes]:
        """Run a converter command and return the output PNG bytes, or None on failure."""
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            log.debug("Conversion failed (%s): %s", cmd[0], e)
            return None
        for path in out_candidates:
            if os.path.exists(path):
                return Path(path).read_bytes()
        return None

    def _convert_wmf_emf_to_png(self, vector_bytes: bytes, ext: str) -> Optional[bytes]:
        """
        Convert WMF/EMF bytes to PNG bytes.
        Tries: Inkscape -> ImageMagick (magick/convert) -> LibreOffice
        """
        if not vector_bytes:
            return None
        if not ext.startswith("."):
            ext = "." + ext

        inkscape = self._which("inkscape")
        magick = self._which("magick", "convert")
        libre = self._which("libreoffice")

        with tempfile.TemporaryDirectory() as td:
            in_path = os.path.join(td, f"in{ext}")
            out_path = os.path.join(td, "out.png")
            libre_out = os.path.join(td, "in.png")
            Path(in_path).write_bytes(vector_bytes)

            # (tool_path, command, timeout, output_candidates)
            magick_cmd = ([magick, in_path, out_path] if "convert" in (magick or "")
                          else [magick, "convert", in_path, out_path])
            converters = [
                (inkscape, [inkscape, in_path, "--export-type=png", f"--export-filename={out_path}"],
                 30, [out_path]),
                (magick, magick_cmd, 30, [out_path]),
                (libre, [libre, "--headless", "--convert-to", "png", "--outdir", td, in_path],
                 60, [libre_out, out_path]),
            ]

            for tool, cmd, timeout, candidates in converters:
                if not tool:
                    continue
                result = self._try_run_converter(cmd, timeout, candidates)
                if result is not None:
                    return result

            log.warning("No WMF/EMF converter available or all conversions failed.")
            return None

    def _resolve_image_bytes_from_rid(
        self,
        r_id: str,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Fetch image bytes by relationship ID, converting WMF/EMF to PNG when needed.
        Uses self._docx_zip and self._rels set during parsing.
        """
        if not r_id or not hasattr(self, "_rels") or not hasattr(self, "_docx_zip"):
            return None, None

        target = self._rels.get(r_id)
        if not target:
            return None, None

        # Resolve the path within the DOCX
        if not target.startswith("/"):
            target = WORD_PREFIX + target
        else:
            target = target.lstrip("/")

        try:
            blob = self._docx_zip.read(target)
        except KeyError:
            log.warning("Image not found in DOCX: %s", target)
            return None, None

        ext = Path(target).suffix.lstrip(".").lower()

        # Convert vector formats
        if ext in ("wmf", "emf"):
            converted = self._convert_wmf_emf_to_png(blob, f".{ext}")
            if converted:
                return converted, "png"
            # Return original if conversion fails
            return blob, ext

        if not ext:
            ext = "png"
        return blob, ext

    # ---------- Diagram/Picture cluster suppression helpers ----------

    @staticmethod
    def _is_outside_textbox(elem, boundary) -> bool:
        """Return True if elem is NOT nested inside a w:txbxContent below boundary."""
        parent = elem.getparent()
        while parent is not None and parent != boundary:
            if parent.tag == create_ns(W_NS, "txbxContent"):
                return False
            parent = parent.getparent()
        return True

    @staticmethod
    def _paragraph_has_visible_text_outside_textbox(p_elem) -> bool:
        """
        True if paragraph has any visible text outside w:txbxContent.
        (We treat text inside shapes/textboxes as not 'paragraph text'.)
        """
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False

        # any w:t / w:delText not inside w:txbxContent counts as visible text
        text_elems = (
            p_elem.findall(f".//{create_ns(W_NS, 't')}")
            + p_elem.findall(f".//{create_ns(W_NS, 'delText')}")
        )
        for t in text_elems:
            if DocxParser._is_outside_textbox(t, p_elem) and (t.text or "").strip():
                return True

        # tabs/br outside textbox also make it non-empty, but rare; keep conservative
        for br in p_elem.findall(f".//{create_ns(W_NS, 'br')}"):
            if DocxParser._is_outside_textbox(br, p_elem):
                return True

        return False

    def _is_drawing_only_paragraph(self, p_elem) -> bool:
        """
        Paragraph that contains drawings/shapes/picts but has no normal text outside textboxes.
        Used to detect picture/diagram clusters (many w:p are only anchors).
        """
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False

        has_drawing = (
            p_elem.find(f".//{create_ns(W_NS,'drawing')}") is not None
            or p_elem.find(f".//{create_ns(W_NS,'pict')}") is not None
            or p_elem.find(f".//{create_ns(V_NS,'shape')}") is not None
        )
        if not has_drawing:
            return False

        return not self._paragraph_has_visible_text_outside_textbox(p_elem)

    # ---------- Crossed-out figure detection ----------

    def _paragraph_image_is_crossed_out(self, p_elem) -> bool:
        """Detect if a paragraph's image is crossed out by a stroke-only overlay.

        Conservative heuristic (high precision, low recall):
          1. Paragraph is drawing-only / drawing-dominant (no normal text).
          2. Exactly 1 image (inline or anchor with blip) in the paragraph.
          3. At least 1 overlay anchor that is:
             - in front (behindDoc != "1")
             - overlap-capable (wrapNone or allowOverlap="1")
             - stroke-only (has ``a:ln``; no blip/pic/imagedata; no txbxContent)
             (2 overlays covers the common "X" cross-out with two diagonal lines.)
          4. All overlays are adjacent to the image in XML run order.
          5. At least one overlay with non-trivial extent is size-compatible
             with the image extent.

        Returns True only when all criteria are satisfied.
        """
        if p_elem is None or p_elem.tag != create_ns(W_NS, "p"):
            return False

        # 1) Must be drawing-only (no real text — page-break-only runs are OK)
        if self._has_visible_text_outside_textbox(p_elem):
            return False

        # 2-3) Collect image holders and overlay anchors across all runs
        image_holders, overlay_anchors = self._collect_image_holders_and_overlays(
            p_elem
        )
        if len(image_holders) != 1 or len(overlay_anchors) < 1:
            return False

        img_cx, img_cy, img_run = image_holders[0]

        # 4) Adjacency: image and overlay(s) must form a contiguous block
        if not self._overlays_are_adjacent_to_image(
            p_elem, img_run, overlay_anchors
        ):
            return False

        # 5) Size compatibility: at least one overlay must match image size
        if not self._any_overlay_is_size_compatible(
            img_cx, img_cy, overlay_anchors
        ):
            return False

        return True

    # -- Crossed-out figure detection: sub-helpers --

    def _has_visible_text_outside_textbox(self, p_elem) -> bool:
        """Return True if paragraph has visible w:t / w:delText outside w:txbxContent.

        This is the Step-1 guard for the crossed-out detection: if the paragraph
        contains real text (not inside a shape textbox), it is not a drawing-only
        paragraph and therefore cannot be a crossed-out image.
        """
        text_elems = (
            list(p_elem.findall(f".//{create_ns(W_NS, 't')}"))
            + list(p_elem.findall(f".//{create_ns(W_NS, 'delText')}"))
        )
        for t in text_elems:
            if self._is_outside_textbox(t, p_elem) and (t.text or "").strip():
                return True
        return False

    def _collect_image_holders_and_overlays(self, p_elem):
        """Walk runs outside textboxes and classify drawing elements.

        Returns
        -------
        tuple[list, list]
            (image_holders, overlay_anchors) — each entry is (cx, cy, run)
            where cx/cy are extent dimensions in EMU.
        """
        image_holders: list = []
        overlay_anchors: list = []

        for run in p_elem.findall(f".//{create_ns(W_NS, 'r')}"):
            # Skip runs inside txbxContent
            if not self._is_outside_textbox(run, p_elem):
                continue

            # Process w:drawing elements (direct children + inside mc:Choice)
            self._classify_drawings_in_run(
                run, image_holders, overlay_anchors
            )

            # OLE images (w:object > v:shape > v:imagedata)
            self._classify_ole_images_in_run(run, image_holders)

        return image_holders, overlay_anchors

    def _classify_drawings_in_run(self, run, image_holders, overlay_anchors):
        """Classify all w:drawing children of run into image holders or overlays.

        Examines both direct ``w:drawing`` children and those nested inside
        ``mc:AlternateContent > mc:Choice``.  Each ``wp:inline`` or ``wp:anchor``
        is categorised by _classify_inline / _classify_anchor.

        Mutates image_holders and overlay_anchors in place.
        """
        drawings: list = list(run.findall(create_ns(W_NS, "drawing")))
        for alt in run.findall(create_ns(MC_NS, "AlternateContent")):
            choice = alt.find(create_ns(MC_NS, "Choice"))
            if choice is not None:
                drawings.extend(choice.findall(create_ns(W_NS, "drawing")))

        for drawing in drawings:
            # Inline images are always image holders
            for inline in drawing.findall(f".//{create_ns(WP_NS, 'inline')}"):
                self._classify_inline(inline, run, image_holders)

            # Anchors can be image holders or stroke-only overlays
            for anchor in drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"):
                self._classify_anchor(anchor, run, image_holders, overlay_anchors)

    @staticmethod
    def _element_has_image_content(elem) -> bool:
        """Return True if elem contains an a:blip, pic:pic, or v:imagedata descendant."""
        return (
            elem.find(f".//{create_ns(A_NS, 'blip')}") is not None
            or elem.find(f".//{create_ns(PIC_NS, 'pic')}") is not None
            or elem.find(f".//{create_ns(V_NS, 'imagedata')}") is not None
        )

    @staticmethod
    def _read_extent(elem) -> tuple:
        """Read (cx, cy) in EMU from the wp:extent child of elem.

        Returns (0, 0) when the extent element is missing.
        """
        ext = elem.find(create_ns(WP_NS, "extent"))
        if ext is None:
            return 0, 0
        return int(ext.get("cx", "0")), int(ext.get("cy", "0"))

    def _classify_inline(self, inline, run, image_holders):
        """If inline carries image content, append it to image_holders."""
        if self._element_has_image_content(inline):
            cx, cy = self._read_extent(inline)
            image_holders.append((cx, cy, run))

    def _classify_anchor(self, anchor, run, image_holders, overlay_anchors):
        """Classify a single wp:anchor as an image holder or a stroke-only overlay.

        Classification rules:
        - If the anchor contains image content (blip / pic / imagedata) → image holder.
        - Otherwise, it is a candidate overlay if ALL of the following hold:
            * Not behind the document (behindDoc != "1").
            * Overlap-capable (has ``wp:wrapNone`` or ``allowOverlap="1"``).
            * No text box content (no ``w:txbxContent`` descendant).
            * Has a line element (``a:ln`` descendant).
        """
        # Anchor-based image → image holder
        if self._element_has_image_content(anchor):
            cx, cy = self._read_extent(anchor)
            image_holders.append((cx, cy, run))
            return

        # --- Candidate stroke-only overlay ---
        if not self._is_stroke_only_overlay(anchor):
            return

        cx, cy = self._read_extent(anchor)
        overlay_anchors.append((cx, cy, run))

    @staticmethod
    def _is_stroke_only_overlay(anchor) -> bool:
        """Return True if anchor qualifies as a stroke-only overlay shape.

        Checks:
        - Not behind the document (behindDoc != "1").
        - Overlap-capable (wrapNone present OR allowOverlap="1").
        - No text box content (no w:txbxContent).
        - Has a line element (a:ln).
        """
        if anchor.get("behindDoc") == "1":
            return False
        has_wrap_none = anchor.find(create_ns(WP_NS, "wrapNone")) is not None
        allow_overlap = anchor.get("allowOverlap") == "1"
        if not (has_wrap_none or allow_overlap):
            return False
        if anchor.find(f".//{create_ns(W_NS, 'txbxContent')}") is not None:
            return False
        if anchor.find(f".//{create_ns(A_NS, 'ln')}") is None:
            return False
        return True

    def _classify_ole_images_in_run(self, run, image_holders):
        """Append OLE-embedded images (w:object > v:shape > v:imagedata) to image_holders.

        Size is resolved from the VML shape ``style`` attribute first, with a
        fallback to the ``dxaOrig`` / ``dyaOrig`` TWIP attributes on w:object.
        """
        for obj in run.findall(create_ns(W_NS, "object")):
            if obj.find(f".//{create_ns(V_NS, 'imagedata')}") is None:
                continue
            cx, cy = self._get_ole_image_extent(obj)
            image_holders.append((cx, cy, run))

    def _get_ole_image_extent(self, obj) -> tuple:
        """Extract (cx, cy) in EMU from an OLE w:object element.

        Tries the v:shape ``style`` attribute (width / height in pt) first.
        Falls back to ``w:dxaOrig`` / ``w:dyaOrig`` (in TWIPs, 1 TWIP = 635 EMU).

        Returns (0, 0) when neither source provides a valid size.
        """
        # Primary: parse from v:shape style
        for vshape in obj.findall(f".//{create_ns(V_NS, 'shape')}"):
            style = vshape.get("style") or ""
            w_raw = self._extract_vml_style_value(style, ("width",))
            h_raw = self._extract_vml_style_value(style, ("height",))
            w_emu = self._parse_pt_to_emu(w_raw)
            h_emu = self._parse_pt_to_emu(h_raw)
            if w_emu > 0 and h_emu > 0:
                return w_emu, h_emu

        # Fallback: TWIP-based original size
        dxa = obj.get(create_ns(W_NS, "dxaOrig"))
        dya = obj.get(create_ns(W_NS, "dyaOrig"))
        try:
            return int(dxa) * 635, int(dya) * 635
        except (ValueError, TypeError):
            return 0, 0

    def _overlays_are_adjacent_to_image(self, p_elem, img_run, overlay_anchors) -> bool:
        """Check that overlay anchors are adjacent to the image in XML run order.

        The image run and all overlay runs must form a contiguous block with no
        visible text in any intervening runs.

        Returns True when adjacency is satisfied (including when all elements
        share the same run).
        """
        all_drawing_runs = [img_run] + [r for _, _, r in overlay_anchors]

        # If everything lives in the same run, adjacency is trivially satisfied
        if all(r is img_run for r in all_drawing_runs):
            return True

        # Build ordered list of top-level runs (outside txbxContent)
        top_runs: list = [
            r for r in p_elem.findall(f".//{create_ns(W_NS, 'r')}")
            if self._is_outside_textbox(r, p_elem)
        ]

        try:
            all_indices = [top_runs.index(r) for r in all_drawing_runs]
        except ValueError:
            return False

        lo, hi = min(all_indices), max(all_indices)

        # Check that intervening runs contain no visible text
        for k in range(lo + 1, hi):
            for t in top_runs[k].findall(create_ns(W_NS, "t")):
                if (t.text or "").strip():
                    return False

        return True

    @staticmethod
    def _any_overlay_is_size_compatible(img_cx, img_cy, overlay_anchors) -> bool:
        """Return True if at least one overlay's extent is size-compatible with the image.

        Size-compatible means the width ratio and height ratio both fall within
        tolerant bounds (0.55–1.8× for width, 0.35–1.8× for height).

        When the image has no measurable extent (cx or cy == 0), compatibility
        is assumed (returns True).
        """
        if img_cx <= 0 or img_cy <= 0:
            # Cannot verify size — assume compatible
            return True

        for ovl_cx, ovl_cy, _ in overlay_anchors:
            if ovl_cx > 0 and ovl_cy > 0:
                w_ratio = ovl_cx / img_cx
                h_ratio = ovl_cy / img_cy
                if 0.55 <= w_ratio <= 1.8 and 0.35 <= h_ratio <= 1.8:
                    return True

        return False

    _CAPTION_PAT = re.compile(
        r"^\s*(?:図|表)\s*[\d.\-]|^\s*(?:figure|fig\.|picture|table)\s*[\d.\-]",
        re.IGNORECASE,
    )

    def _is_caption_text(self, text: str) -> bool:
        if not text:
            return False
        return self._CAPTION_PAT.search(text.strip()) is not None

    # ---------- Structural shape property helpers ----------

    @staticmethod
    def _wsp_is_diagram_content(wsp) -> bool:
        """
        Return True if a wps:wsp shape is a diagram/flowchart element rather
        than a caption/annotation overlay.

        Structural heuristic (no text inspection):
          - Diagram shapes have a visible border  (a:ln with a:solidFill).
          - Caption text boxes are borderless or have transparent fill.
        """
        sp_pr = wsp.find(create_ns(WPS_NS, "spPr"))
        if sp_pr is None:
            return False

        ln = sp_pr.find(create_ns(A_NS, "ln"))
        if ln is not None and ln.find(create_ns(A_NS, "solidFill")) is not None:
            return True

        return False

    @staticmethod
    def _vshape_is_diagram_content(vshape) -> bool:
        """
        Return True if a VML shape / rect / oval is a diagram element.

        Structural heuristic:
          - stroked="t"  -> visible border
          - strokecolor="..."  -> visible border
        """
        stroked = (vshape.get("stroked") or "").lower()
        if stroked in ("t", "true", "1"):
            return True
        if vshape.get("strokecolor"):
            return True
        return False

    @staticmethod
    def _is_inside_alternate_content(elem) -> bool:
        """Return True if elem has an mc:AlternateContent ancestor."""
        parent = elem.getparent()
        while parent is not None:
            if parent.tag == create_ns(MC_NS, "AlternateContent"):
                return True
            parent = parent.getparent()
        return False

    def _collect_caption_texts_from_drawing(self, drawing) -> List[str]:
        """Return caption texts from wps:wsp shapes inside a single w:drawing."""
        texts: List[str] = []
        holders = (
            list(drawing.findall(f".//{create_ns(WP_NS, 'inline')}"))
            + list(drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"))
        )
        for holder in holders:
            for wsp in holder.findall(f".//{create_ns(WPS_NS, 'wsp')}"):
                if self._wsp_is_diagram_content(wsp):
                    continue
                txbx = wsp.find(create_ns(WPS_NS, "txbx"))
                txbx_content = txbx.find(create_ns(W_NS, "txbxContent")) if txbx is not None else None
                st = self._extract_text_from_txbx_content(txbx_content)
                if st and not self._is_marker_shape_text(st):
                    texts.append(st)
        return texts

    def _collect_caption_texts_from_vml_shape(self, vel) -> List[str]:
        """Return caption texts from v:textbox elements inside a VML shape."""
        if self._vshape_is_diagram_content(vel):
            return []
        texts: List[str] = []
        for textbox in vel.findall(f".//{create_ns(V_NS, 'textbox')}"):
            txbx_content = textbox.find(create_ns(W_NS, "txbxContent"))
            if txbx_content is None:
                continue
            st = self._extract_text_from_txbx_content(txbx_content)
            if st and not self._is_marker_shape_text(st):
                texts.append(st)
        return texts

    @staticmethod
    def _dedup_and_filter_captions(candidates: List[str], caption_filter) -> str:
        """Deduplicate candidates, keep only those matching the caption filter, return joined text."""
        seen: Set[str] = set()
        kept: List[str] = []
        for s in candidates:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                kept.append(s)
        caption_kept = [s for s in kept if caption_filter(s)]
        return " ".join(caption_kept).strip() if caption_kept else ""

    def _extract_caption_text_from_paragraph(self, p_elem) -> str:
        """
        Extract ONLY caption/annotation shape text from a drawing-only paragraph.

        Uses structural shape properties (border / fill transparency) to
        separate captions from diagram content.

        Caption shapes: borderless text boxes or transparent-fill overlays.
        Diagram shapes: bordered flowchart boxes, process steps, arrows.
        """
        if not self.get_shape_content:
            return ""

        candidates: List[str] = []
        candidates.extend(self._extract_captions_from_alternate_content(p_elem))
        candidates.extend(self._extract_captions_from_direct_drawings(p_elem))
        candidates.extend(self._extract_captions_from_vml_shapes(p_elem))

        return self._dedup_and_filter_captions(candidates, self._is_caption_text)

    def _extract_captions_from_alternate_content(self, p_elem) -> List[str]:
        """
        Extract caption texts from drawings inside mc:AlternateContent > mc:Choice.
        """
        candidates: List[str] = []

        for alt in p_elem.findall(f".//{create_ns(MC_NS, 'AlternateContent')}"):
            choice = alt.find(create_ns(MC_NS, "Choice"))
            if choice is None:
                continue

            for drawing in choice.findall(f".//{create_ns(W_NS, 'drawing')}"):
                candidates.extend(self._collect_caption_texts_from_drawing(drawing))

        return candidates

    def _extract_captions_from_direct_drawings(self, p_elem) -> List[str]:
        """
        Extract caption texts from direct w:drawing elements that are not inside
        mc:AlternateContent.
        """
        candidates: List[str] = []

        for drawing in p_elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if self._is_inside_alternate_content(drawing):
                continue
            candidates.extend(self._collect_caption_texts_from_drawing(drawing))

        return candidates

    def _extract_captions_from_vml_shapes(self, p_elem) -> List[str]:
        """
        Extract caption texts from VML shapes not inside mc:AlternateContent.
        """
        candidates: List[str] = []

        for tag in ("shape", "rect", "oval"):
            for vel in p_elem.findall(f".//{create_ns(V_NS, tag)}"):
                if self._is_inside_alternate_content(vel):
                    continue
                candidates.extend(self._collect_caption_texts_from_vml_shape(vel))

        return candidates

    # Set of single-character markers that should be ignored in shape text extraction.
    # These are typically used as revision markers, status indicators, or decorative elements
    # inside small text boxes overlaid on diagrams/shapes in the document.
    # Examples: Triangle with "R" inside for "Revision", etc.
    SHAPE_TEXT_MARKERS_TO_IGNORE = frozenset({"R",})

    def _is_marker_shape_text(self, text: str) -> bool:
        """
        Check if the extracted shape text is a marker that should be ignored.

        Marker shapes are typically small text boxes containing single characters
        like "R" (revision marker) that are used as visual indicators in diagrams
        and should not be extracted as document content.
        """
        stripped = text.strip()
        if stripped in self.SHAPE_TEXT_MARKERS_TO_IGNORE:
            return True
        return False

    @staticmethod
    def _is_inside_del(r, boundary) -> bool:
        """Return True if r is nested inside a w:del element below boundary."""
        parent = r.getparent()
        while parent is not None and parent != boundary:
            if parent.tag == create_ns(W_NS, "del"):
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _collect_run_text_tokens(r) -> List[str]:
        """Collect text from w:t and w:delText children of a single run."""
        tokens: List[str] = []
        for t in r.findall(create_ns(W_NS, "t")):
            if t.text:
                tokens.append(t.text)
        for dt in r.findall(create_ns(W_NS, "delText")):
            if dt.text:
                tokens.append(dt.text)
        return tokens

    @classmethod
    def _extract_txbx_paragraph_text(cls, p) -> str:
        """Extract text from a single paragraph inside a txbxContent, skipping deleted and field-cached runs."""
        para_parts: List[str] = []
        field_stack: List[dict] = []

        for r in p.findall(f".//{create_ns(W_NS, 'r')}"):
            if cls._is_inside_del(r, p):
                continue
            cls._update_field_stack(r, field_stack)
            if cls._is_run_in_skipped_field(field_stack):
                continue
            para_parts.extend(cls._collect_run_text_tokens(r))

        return "".join(para_parts).strip()

    def _extract_text_from_txbx_content(self, txbx_content) -> str:
        """
        Extract text from a w:txbxContent element (text box content inside shapes).
        Parses all paragraphs within the text box and joins them.
        """
        if txbx_content is None:
            return ""

        text_parts = []
        for p in txbx_content.findall(f".//{create_ns(W_NS, 'p')}"):
            para_text = self._extract_txbx_paragraph_text(p)
            if para_text:
                text_parts.append(para_text)

        return " ".join(text_parts)

    def _extract_shapes_from_element(self, elem) -> List[str]:
        """
        Extract shape text content from an element (paragraph or run).

        Looks for:
        - modern shapes inside mc:AlternateContent > mc:Choice > w:drawing
        - direct w:drawing elements not inside mc:AlternateContent
        - VML fallback shapes with v:textbox > w:txbxContent

        Returns
        -------
        List[str]
            Shape-content placeholder strings.
        """
        if not self.get_shape_content:
            return []

        shape_chunks: List[str] = []
        shape_chunks.extend(self._extract_shapes_from_alternate_content(elem))
        shape_chunks.extend(self._extract_shapes_from_direct_drawings(elem))
        shape_chunks.extend(self._extract_shapes_from_vml_fallback(elem))
        return shape_chunks

    def _extract_shapes_from_alternate_content(self, elem) -> List[str]:
        """
        Extract shape chunks from mc:AlternateContent > mc:Choice drawings.
        """
        shape_chunks: List[str] = []

        for alt_content in elem.findall(f".//{create_ns(MC_NS, 'AlternateContent')}"):
            choice = alt_content.find(create_ns(MC_NS, "Choice"))
            if choice is None:
                continue

            for drawing in choice.findall(f".//{create_ns(W_NS, 'drawing')}"):
                shape_text = self._extract_shape_text_from_drawing(drawing)
                wrapped = self._wrap_shape_text(shape_text)
                if wrapped:
                    shape_chunks.append(wrapped)

        return shape_chunks

    def _extract_shapes_from_direct_drawings(self, elem) -> List[str]:
        """
        Extract shape chunks from direct w:drawing elements that are not inside
        mc:AlternateContent.
        """
        shape_chunks: List[str] = []

        for drawing in elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if self._is_inside_alternate_content(drawing):
                continue

            shape_text = self._extract_shape_text_from_drawing(drawing)
            wrapped = self._wrap_shape_text(shape_text)
            if wrapped:
                shape_chunks.append(wrapped)

        return shape_chunks

    def _extract_shapes_from_vml_fallback(self, elem) -> List[str]:
        """
        Extract shape chunks from VML fallback shapes not inside
        mc:AlternateContent.
        """
        shape_chunks: List[str] = []

        for vshape in elem.findall(f".//{create_ns(V_NS, 'shape')}"):
            if self._is_inside_alternate_content(vshape):
                continue

            for textbox in vshape.findall(f".//{create_ns(V_NS, 'textbox')}"):
                txbx_content = textbox.find(create_ns(W_NS, "txbxContent"))
                if txbx_content is None:
                    continue

                shape_text = self._extract_text_from_txbx_content(txbx_content)
                if not shape_text or self._is_marker_shape_text(shape_text):
                    continue

                wrapped = self._wrap_shape_text(shape_text)
                if wrapped:
                    shape_chunks.append(wrapped)

        return shape_chunks

    @staticmethod
    def _wrap_shape_text(shape_text: str) -> str:
        """
        Wrap non-empty shape text with shape content markers.

        Parameters
        ----------
        shape_text : str
            Extracted shape text.

        Returns
        -------
        str
            Wrapped shape text, or an empty string if shape_text is empty.
        """
        if not shape_text:
            return ""
        return f"{SHAPE_CONTENT_START_MARKER} {shape_text} {SHAPE_CONTENT_END_MARKER}"

    @staticmethod
    def _is_inside_alternate_content(elem) -> bool:
        """
        Check whether an element is nested inside mc:AlternateContent.

        Parameters
        ----------
        elem : lxml element
            Element to inspect.

        Returns
        -------
        bool
            True if the element has an mc:AlternateContent ancestor.
        """
        parent = elem.getparent()
        while parent is not None:
            if parent.tag == create_ns(MC_NS, "AlternateContent"):
                return True
            parent = parent.getparent()
        return False

    def _extract_shape_text_from_drawing(self, drawing) -> str:
        """
        Extract text from a w:drawing element containing shapes with text boxes.
        Handles both wp:anchor (floating) and wp:inline (in-line) shapes.
        Returns the extracted text or empty string if no text content.

        Note: Marker shapes (e.g., small text boxes with single characters like "R")
        are filtered out as they are typically revision markers or decorative elements.
        """
        # Look for inline and anchor holders
        holders = (
            list(drawing.findall(f".//{create_ns(WP_NS, 'inline')}"))
            + list(drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"))
        )

        text_parts = []
        for holder in holders:
            # Look for wps:wsp (WordprocessingML shape) with wps:txbx
            for wsp in holder.findall(f".//{create_ns(WPS_NS, 'wsp')}"):
                txbx = wsp.find(create_ns(WPS_NS, "txbx"))
                txbx_content = txbx.find(create_ns(W_NS, "txbxContent")) if txbx is not None else None
                shape_text = self._extract_text_from_txbx_content(txbx_content) if txbx_content is not None else None
                # Skip marker shapes (single-character markers like "R")
                if shape_text and not self._is_marker_shape_text(shape_text):
                    text_parts.append(shape_text)

        return " ".join(text_parts)

    def _extract_images_from_element(self, elem) -> List[str]:
        """
        Extract image placeholders from an element (paragraph or run).

        Supported image sources:
        1. DrawingML images:
        w:drawing -> wp:inline/wp:anchor -> a:blip
        2. VML / OLE preview images:
        w:pict or w:object -> v:imagedata

        Returns:
            List[str]:
                A list of image placeholder strings.
        """
        if not self.get_image_content:
            return []

        image_chunks: List[str] = []
        image_chunks.extend(self._extract_drawingml_image_placeholders(elem))
        image_chunks.extend(self._extract_vml_ole_image_placeholders(elem))
        return image_chunks


    def _extract_drawingml_image_placeholders(self, elem) -> List[str]:
        """
        Extract image placeholders from DrawingML content.

        Structure handled:
            w:drawing
            -> wp:inline or wp:anchor
                -> a:blip with r:embed or r:link

        Variable legend:
            drawing:
                A single w:drawing element.
            holder:
                A wp:inline or wp:anchor element containing renderable drawing content.
            blip:
                An a:blip element that references image data by relationship ID.
            rel_id:
                Relationship ID obtained from r:embed or r:link.
        """
        image_chunks: List[str] = []

        for drawing in elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            holders = self._find_drawing_holders(drawing)
            for holder in holders:
                image_chunks.extend(self._extract_blip_placeholders_from_holder(holder))

        return image_chunks


    def _extract_vml_ole_image_placeholders(self, elem) -> List[str]:
        """
        Extract image placeholders from VML images and OLE preview images.

        Structures handled:
            w:pict   -> v:imagedata
            w:object -> v:imagedata

        Variable legend:
            container_tag:
                Either 'pict' or 'object'.
            container:
                A w:pict or w:object element.
            imgdata:
                A v:imagedata element referencing image bytes through r:id.
            rel_id:
                Relationship ID obtained from the v:imagedata r:id attribute.
        """
        image_chunks: List[str] = []

        for container_tag in ("pict", "object"):
            for container in elem.findall(f".//{create_ns(W_NS, container_tag)}"):
                for imgdata in container.findall(f".//{create_ns(V_NS, 'imagedata')}"):
                    rel_id = imgdata.get(create_ns(R_NS, "id"))
                    placeholder = self._resolve_image_placeholder(rel_id)
                    if placeholder:
                        image_chunks.append(placeholder)

        return image_chunks

    @staticmethod
    def _find_drawing_holders(drawing) -> List:
        """
        Return all DrawingML holders inside a w:drawing element.

        A holder is one of:
            - wp:inline
            - wp:anchor
        """
        return (
            list(drawing.findall(f".//{create_ns(WP_NS, 'inline')}"))
            + list(drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"))
        )


    def _extract_blip_placeholders_from_holder(self, holder) -> List[str]:
        """
        Extract image placeholders from all a:blip elements inside one holder.

        Variable legend:
            holder:
                A wp:inline or wp:anchor element.
            blip:
                An a:blip element.
            rel_id:
                Relationship ID obtained from r:embed or r:link.
            placeholder:
                Resolved image placeholder string, or None if resolution fails.
        """
        image_chunks: List[str] = []

        for blip in holder.findall(f".//{create_ns(A_NS, 'blip')}"):
            rel_id = blip.get(create_ns(R_NS, "embed")) or blip.get(create_ns(R_NS, "link"))
            placeholder = self._resolve_image_placeholder(rel_id)
            if placeholder:
                image_chunks.append(placeholder)

        return image_chunks

    def _has_paragraph_strike_style(self, p_elem) -> bool:
        """Return True if the paragraph's style is a known strikethrough style."""
        if self.keep_strikethrough_text:
            return False
        ppr = p_elem.find(create_ns(W_NS, "pPr"))
        pstyle = ppr.find(create_ns(W_NS, "pStyle")) if ppr is not None else None
        style_val = pstyle.get(create_ns(W_NS, "val")) if pstyle is not None else None
        return bool(style_val and style_val in self._strike_style_ids)

    def _is_inside_textbox_or_struck_run(self, elem, boundary) -> bool:
        """Walk ancestors from elem up to (but not including) boundary.

        Return True if elem is nested inside a ``w:txbxContent`` element
        or its containing ``w:r`` run has strikethrough formatting.
        """
        parent = elem.getparent()
        while parent is not None and parent != boundary:
            if parent.tag == create_ns(W_NS, "txbxContent"):
                return True
            if (
                not self.keep_strikethrough_text
                and parent.tag == create_ns(W_NS, "r")
            ):
                rpr = parent.find(create_ns(W_NS, "rPr"))
                if _elem_has_any_child(rpr, W_NS, "strike", "dstrike"):
                    return True
            parent = parent.getparent()
        return False

    def _resolve_image_placeholder(self, rel_id: Optional[str]) -> Optional[str]:
        """Resolve a relationship ID to an image-path placeholder string.

        Checks the per-rid cache, then the content-hash cache, and finally
        saves brand-new bytes.

        Returns None when rel_id is missing or when no image bytes can be obtained.
        """
        if not rel_id:
            return None
        # 1. Fast path: already resolved this rel_id
        cached = self._image_cache_by_rid.get(rel_id)
        if cached:
            image_path, image_hash = cached
            return f"{IMG_PATH_START_MARKER} {image_path}|{image_hash} {IMG_PATH_END_MARKER}"

        # 2. Resolve raw bytes
        image_bytes, image_ext = self._resolve_image_bytes_from_rid(rel_id)
        if not image_bytes:
            return None

        # 3. Deduplicate by content hash
        image_hash = self._md5(image_bytes)
        existing_path = self._image_cache_by_hash.get(image_hash)
        if existing_path:
            self._image_cache_by_rid[rel_id] = (existing_path, image_hash)
            return f"{IMG_PATH_START_MARKER} {existing_path}|{image_hash} {IMG_PATH_END_MARKER}"

        # 4. Save new image
        saved = self._save_image_bytes(image_bytes, image_ext, rel_id=rel_id)
        if saved:
            image_path, saved_hash = saved
            self._image_cache_by_rid[rel_id] = (image_path, saved_hash)
            self._image_cache_by_hash[saved_hash] = image_path
            return f"{IMG_PATH_START_MARKER} {image_path}|{saved_hash} {IMG_PATH_END_MARKER}"

        return f"{IMG_PATH_START_MARKER} MISSING_IMAGE {IMG_PATH_END_MARKER}"

    def _collect_drawing_image_placeholders(self, p_elem, image_chunks: List[str]) -> None:
        """Collect image placeholders from ``w:drawing`` elements."""
        for drawing in p_elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if self._is_inside_textbox_or_struck_run(drawing, p_elem):
                continue

            holders = (
                list(drawing.findall(f".//{create_ns(WP_NS, 'inline')}"))
                + list(drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"))
            )

            for holder in holders:
                for blip in holder.findall(f".//{create_ns(A_NS, 'blip')}"):
                    rel_id = blip.get(create_ns(R_NS, "embed")) or blip.get(create_ns(R_NS, "link"))
                    placeholder = self._resolve_image_placeholder(rel_id)
                    if placeholder:
                        image_chunks.append(placeholder)

    def _collect_vml_image_placeholders(self, p_elem, image_chunks: List[str], container_tag: str) -> None:
        """Collect image placeholders from VML ``v:imagedata`` inside container_tag elements.

        container_tag is the local name of the container, e.g. ``"pict"`` or ``"object"``.
        """
        for container in p_elem.findall(f".//{create_ns(W_NS, container_tag)}"):
            if self._is_inside_textbox_or_struck_run(container, p_elem):
                continue

            for imgdata in container.findall(f".//{create_ns(V_NS, 'imagedata')}"):
                rel_id = imgdata.get(create_ns(R_NS, "id"))
                if not rel_id:
                    continue
                placeholder = self._resolve_image_placeholder(rel_id)
                if placeholder:
                    image_chunks.append(placeholder)

    def _extract_images_from_paragraph(self, p_elem) -> List[str]:
        """
        Extract image placeholders from a paragraph element.

        Used by flush_pending_drawing_ps to emit IMAGE_PATH markers for images
        found inside picture/diagram clusters (drawing-only paragraphs).
        Skips drawings that are inside w:txbxContent (textbox shapes).
        Skips drawings whose containing run has strikethrough formatting.
        """
        if not self.get_image_content or self._paragraph_image_is_crossed_out(p_elem):
            return []

        if self._has_paragraph_strike_style(p_elem):
            return []

        image_chunks: List[str] = []

        # DrawingML images (w:drawing > wp:inline/wp:anchor > a:blip)
        self._collect_drawing_image_placeholders(p_elem, image_chunks)

        # VML images (w:pict > v:shape > v:imagedata)
        self._collect_vml_image_placeholders(p_elem, image_chunks, "pict")

        # OLE object images (w:object > v:shape > v:imagedata)
        self._collect_vml_image_placeholders(p_elem, image_chunks, "object")

        return image_chunks

    def _iter_candidate_drawings_from_paragraph(self, p_elem):
        """
        Yield drawings to inspect from a paragraph:
        1. drawings inside mc:AlternateContent > mc:Choice
        2. direct drawings not nested inside mc:AlternateContent
        """
        for alt in p_elem.findall(f".//{create_ns(MC_NS, 'AlternateContent')}"):
            choice = alt.find(create_ns(MC_NS, "Choice"))
            if choice is None:
                continue

            for drawing in choice.findall(f".//{create_ns(W_NS, 'drawing')}"):
                yield drawing

        for drawing in p_elem.findall(f".//{create_ns(W_NS, 'drawing')}"):
            if not self._element_is_inside_alternate_content(drawing):
                yield drawing

    @staticmethod
    def _element_is_inside_alternate_content(elem) -> bool:
        """
        Return True if the given element has an mc:AlternateContent ancestor.
        """
        parent = elem.getparent()
        while parent is not None:
            if parent.tag == create_ns(MC_NS, "AlternateContent"):
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _iter_drawing_holders(drawing):
        """
        Yield wp:inline and wp:anchor holders under a drawing.
        """
        for holder in drawing.findall(f".//{create_ns(WP_NS, 'inline')}"):
            yield holder
        for holder in drawing.findall(f".//{create_ns(WP_NS, 'anchor')}"):
            yield holder

    def _extract_substantial_text_from_wsp(
        self,
        wsp,
        min_text_length: int,
    ) -> str | None:
        """
        Return stripped textbox text from a diagram-content wsp if it is substantial.
        Otherwise return None.
        """
        if not self._wsp_is_diagram_content(wsp):
            return None

        txbx = wsp.find(create_ns(WPS_NS, "txbx"))
        txbx_content = txbx.find(create_ns(W_NS, "txbxContent")) if txbx is not None else None
        text = self._extract_text_from_txbx_content(txbx_content)
        if text is not None:
            stripped_text = text.strip()
            if len(stripped_text) >= min_text_length:
                return stripped_text

        return None

    def _extract_substantial_shape_text_from_paragraph(
        self, p_elem, min_text_length: int = 100
    ) -> List[str]:
        if not self.get_shape_content:
            return []

        results: List[str] = []

        for drawing in self._iter_candidate_drawings_from_paragraph(p_elem):
            for holder in self._iter_drawing_holders(drawing):
                for wsp in holder.findall(f".//{create_ns(WPS_NS, 'wsp')}"):
                    text = self._extract_substantial_text_from_wsp(
                        wsp,
                        min_text_length=min_text_length,
                    )
                    if text:
                        results.append(text)

        return results

    def _extract_bookmarks(self, root) -> List[Dict[str, Any]]:
        """Extract all bookmarks from the document."""
        bookmarks = []
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        # Find all bookmarkStart elements
        for bm_start in root.xpath('//w:bookmarkStart', namespaces=ns):
            bm_id = bm_start.get(f"{{{ns['w']}}}id")
            bm_name = bm_start.get(f"{{{ns['w']}}}name")
            if bm_name:
                bookmarks.append({"name": bm_name})

        return bookmarks

    def _extract_track_changes(self, root) -> List[Dict[str, Any]]:
        """Extract track changes from the document."""
        track_changes = []
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        # Find all track change elements (ins, del, moveFrom, moveTo)
        for elem in root.xpath('//w:ins | //w:del | //w:moveFrom | //w:moveTo', namespaces=ns):
            change_type = elem.tag.replace(f"{{{ns['w']}}}", "")
            change_data = {"type": change_type}

            # Extract author if available
            author = elem.get(f"{{{ns['w']}}}author")
            if author:
                change_data["author"] = author

            # Extract date if available
            date = elem.get(f"{{{ns['w']}}}date")
            if date:
                change_data["date"] = date

            # Extract text content
            text = self._node_text_content(elem)
            if text:
                change_data["text"] = text

            track_changes.append(change_data)

        return track_changes

    def get_bookmarks_and_track_changes(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return collected bookmarks and track changes."""
        return self._bookmarks, self._track_changes


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Parse DOCX files")
    parser.add_argument("--input", help="Path to DOCX file")
    parser.add_argument("--gray-brightness", type=float, default=180.0)
    parser.add_argument("--gray-spread", type=int, default=12)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    docx_parser = DocxParser(drop_deleted_table_content=True)
    docx_parser.gray_brightness_thr = args.gray_brightness
    docx_parser.gray_spread_thr = args.gray_spread

    tree = docx_parser.extract_docx_text(args.input)

    in_path = Path(args.input)
    parts = list(in_path.parts)
    if "raw" in parts:
        idx = parts.index("raw")
        parts[idx] = "output_parsed"
        out_base = Path(*parts[:-1])
    else:
        # fallback: put under sibling output_parsed next to input parent
        out_base = in_path.parent / "output_parsed"

    out_base.mkdir(parents=True, exist_ok=True)

    out_json_path = out_base / f"{in_path.stem}.json"

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    log.info(f"[SUCCESS] Output saved to {out_json_path}")

if __name__ == "__main__":
    main()
