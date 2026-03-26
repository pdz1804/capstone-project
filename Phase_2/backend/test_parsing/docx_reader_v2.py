"""
DOCX reader and extractor utilities (No python-docx dependency).
This module provides tools to parse Microsoft Word (.docx) files by directly
reading the underlying XML structure. Key features include:
- Direct XML parsing of document.xml, numbering.xml, styles.xml
- Paragraph and heading extraction with hierarchy
- Table extraction as Markdown
- Image extraction (saved to disk)
- Numbering/list marker resolution
- Strikethrough and revision tracking
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
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from lxml import etree
from dataclasses import dataclass

# Namespaces
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
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

SHAPE_CONTENT_START_MARKER = "[START_SHAPE_CONTENT]"
SHAPE_CONTENT_END_MARKER = "[END_SHAPE_CONTENT]"
IMAGE_PATH_START_MARKER = "[START_IMAGE_PATH]"
IMAGE_PATH_END_MARKER = "[END_IMAGE_PATH]"

LVL_TEXT_PATTERN = re.compile(r"%(\d+)")
log = logging.getLogger(__name__)

def ns(namespace: str, tag: str) -> str:
    """Helper to create namespaced XML tags."""
    return f"{{{namespace}}}{tag}"


@dataclass
class FillSpec:
    """A normalized shading specification found in w:shd."""
    fill_hex: str = ""         # explicit RGB like "A6A6A6"
    theme_fill: str = ""       # e.g. "background1", "accent1"
    theme_shade: str = ""      # 2-hex like "A6"
    theme_tint: str = ""       # 2-hex like "40"
    source: str = ""           # debug: where this spec came from (tc/tr/style)

class ThemeResolver:
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
            key = etree.QName(child).localname  # dk1, lt1, accent1...
            # sysClr lastClr or srgbClr val
            sysclr = child.find(f".//{{{A_NS}}}sysClr")
            srgb = child.find(f".//{{{A_NS}}}srgbClr")
            hexval = ""
            if sysclr is not None:
                hexval = sysclr.get("lastClr", "") or ""
            if not hexval and srgb is not None:
                hexval = srgb.get("val", "") or ""
            hexval = hexval.strip().upper()
            if re.fullmatch(r"[0-9A-F]{6}", hexval):
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
        if spec.fill_hex and re.fullmatch(r"[0-9A-Fa-f]{6}", spec.fill_hex):
            return spec.fill_hex.upper()

        if not spec.theme_fill:
            return ""

        word_key = spec.theme_fill.strip()
        scheme_key = self.WORD_TO_SCHEME.get(word_key, "")
        base = self.scheme_rgb.get(scheme_key, "")
        if not base:
            return ""

        rgb = self._hex_to_rgb(base)

        if spec.theme_shade and re.fullmatch(r"[0-9A-Fa-f]{2}", spec.theme_shade):
            rgb = self._apply_shade(rgb, int(spec.theme_shade, 16))
        if spec.theme_tint and re.fullmatch(r"[0-9A-Fa-f]{2}", spec.theme_tint):
            rgb = self._apply_tint(rgb, int(spec.theme_tint, 16))

        return self._rgb_to_hex(*rgb)

class TableStyleHelper:
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

    def _parse_shd(self, shd_el, source: str) -> FillSpec:
        if shd_el is None:
            return FillSpec()

        fill = (shd_el.get(ns(W_NS, "fill")) or shd_el.get("fill") or "").strip().upper()
        theme_fill = (shd_el.get(ns(W_NS, "themeFill")) or shd_el.get("themeFill") or "").strip()
        theme_shade = (shd_el.get(ns(W_NS, "themeFillShade")) or shd_el.get("themeFillShade") or "").strip()
        theme_tint = (shd_el.get(ns(W_NS, "themeFillTint")) or shd_el.get("themeFillTint") or "").strip()

        if fill and not re.fullmatch(r"[0-9A-F]{6}", fill):
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

        for style in root.findall(ns(W_NS, "style")):
            if style.get(ns(W_NS, "type")) != "table":
                continue

            style_id = style.get(ns(W_NS, "styleId"))
            if not style_id:
                continue

            # DEFAULT shading: ONLY direct child <w:tcPr><w:shd/>
            shd_default = style.find(f"./{ns(W_NS,'tcPr')}/{ns(W_NS,'shd')}")
            spec_default = self._parse_shd(shd_default, source=f"style:{style_id}:default")
            if spec_default.fill_hex or spec_default.theme_fill:
                self.default_spec[style_id] = spec_default

            # CONDITIONAL shading: tblStylePr[@type] / tcPr / shd
            cond_map: Dict[str, FillSpec] = {}
            for tsp in style.findall(ns(W_NS, "tblStylePr")):
                tname = tsp.get(ns(W_NS, "type"))
                if not tname:
                    continue

                shd_cond = tsp.find(f"./{ns(W_NS,'tcPr')}/{ns(W_NS,'shd')}")
                spec_cond = self._parse_shd(shd_cond, source=f"style:{style_id}:{tname}")
                if spec_cond.fill_hex or spec_cond.theme_fill:
                    cond_map[tname] = spec_cond

            if cond_map:
                self.conditional_spec[style_id] = cond_map

    def resolve_spec(self, style_id: str, cnf_attrs: Dict[str, str]) -> FillSpec:
        if not style_id:
            return FillSpec()

        cond = self.conditional_spec.get(style_id, {})

        # match most specific first
        for cnf_key, tname in self.CNF_TO_TYPES:
            if cnf_attrs.get(cnf_key) in {"1", "true", "on"} and tname in cond:
                return cond[tname]

        return self.default_spec.get(style_id, FillSpec())

class NumberingHelper:
    """Resolve Word numbering definitions so list/heading markers are emitted as text."""

    def __init__(self, numbering_xml: Optional[bytes]):
        # levels[numId][ilvl] = {lvlText,numFmt,start,suffix,restart}
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
        abstract_levels: Dict[str, Dict[int, Dict[str, Union[str, int, None]]]] = {}
        for abstract in root.findall(ns(W_NS, 'abstractNum')):
            abstract_id = abstract.get(ns(W_NS, 'abstractNumId'))
            if not abstract_id:
                continue
            abstract_levels[abstract_id] = self._parse_abstract_levels(abstract)

        # 2) Parse num instances + apply overrides (lvlOverride / startOverride)
        for num in root.findall(ns(W_NS, 'num')):
            num_id = num.get(ns(W_NS, 'numId'))
            if not num_id:
                continue
            abstract_id_el = num.find(ns(W_NS, 'abstractNumId'))
            if abstract_id_el is None:
                continue
            abstract_id = abstract_id_el.get(ns(W_NS, 'val'))
            if not abstract_id:
                continue
            self.num_to_abstract[str(num_id)] = abstract_id

            levels = dict(abstract_levels.get(abstract_id, {}))

            # Apply lvlOverride: may redefine lvl properties and/or startOverride
            for override in num.findall(ns(W_NS, 'lvlOverride')):
                ilvl_attr = override.get(ns(W_NS, 'ilvl'))
                if ilvl_attr is None:
                    continue
                try:
                    ilvl = int(ilvl_attr)
                except ValueError:
                    continue

                # startOverride
                start_override_el = override.find(ns(W_NS, 'startOverride'))
                if start_override_el is not None:
                    start_val = start_override_el.get(ns(W_NS, 'val'))
                    if start_val is not None:
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

                # full lvl override
                lvl_el = override.find(ns(W_NS, 'lvl'))
                if lvl_el is not None:
                    _, info = self._parse_single_level(lvl_el)
                    levels[ilvl] = info

            if levels:
                self.levels[str(num_id)] = levels

    def _parse_abstract_levels(self, abstract_elem) -> Dict[int, Dict[str, Union[str, int, None]]]:
        levels: Dict[int, Dict[str, Union[str, int, None]]] = {}
        for lvl in abstract_elem.findall(ns(W_NS, 'lvl')):
            ilvl, info = self._parse_single_level(lvl)
            levels[ilvl] = info
        return levels

    def _parse_single_level(self, lvl_el) -> Tuple[int, Dict[str, Union[str, int, None]]]:
        ilvl_raw = lvl_el.get(ns(W_NS, 'ilvl'))
        try:
            ilvl = int(ilvl_raw) if ilvl_raw is not None else 0
        except ValueError:
            ilvl = 0

        # lvlText
        lvl_text_el = lvl_el.find(ns(W_NS, 'lvlText'))
        lvl_text = (lvl_text_el.get(ns(W_NS, 'val')) if lvl_text_el is not None else None)

        # numFmt
        fmt_el = lvl_el.find(ns(W_NS, 'numFmt'))
        num_fmt = (fmt_el.get(ns(W_NS, 'val')) if fmt_el is not None else 'decimal')

        # start
        start_el = lvl_el.find(ns(W_NS, 'start'))
        start = 1
        if start_el is not None:
            v = start_el.get(ns(W_NS, 'val'))
            try:
                start = int(v) if v is not None else 1
            except ValueError:
                start = 1

        # suffix
        suff_el = lvl_el.find(ns(W_NS, 'suff'))
        suffix = (suff_el.get(ns(W_NS, 'val')) if suff_el is not None else '')

        # lvlRestart
        restart_el = lvl_el.find(ns(W_NS, 'lvlRestart'))
        restart = None
        if restart_el is not None:
            rv = restart_el.get(ns(W_NS, 'val'))
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
            idx = int(m.group(1)) - 1  # %1 -> ilvl 0
            val = counters.get(idx)
            fmt = level_map.get(idx, {}).get('numFmt') if idx in level_map else 'decimal'
            return self._format_value(val, str(fmt) if fmt is not None else 'decimal')

        return LVL_TEXT_PATTERN.sub(repl, str(tmpl))

    def get_marker(self, num_id: str, ilvl: int) -> str:
        """Return the marker string for a given numId + level, updating counters correctly."""
        if num_id not in self.levels:
            return '•'
        level_map = self.levels[num_id]
        if ilvl not in level_map:
            return '•'

        level_info = level_map[ilvl]
        start = level_info.get('start', 1)
        try:
            start_int = int(start) if start is not None else 1
        except (TypeError, ValueError):
            start_int = 1

        abstract_id = self.num_to_abstract.get(num_id)
        abstract_state = self.abstract_counters[abstract_id] if abstract_id else None
        counters = self.counters[num_id]

        # Drop deeper levels when we move up
        for k in list(counters.keys()):
            if k > ilvl:
                counters.pop(k, None)
        if abstract_state is not None:
            for k in list(abstract_state.keys()):
                if k > ilvl:
                    abstract_state.pop(k, None)

        # Ensure parent levels exist
        # When multiple numIds share the same abstractNumId, they should share counter state.
        # Prioritize reading from abstract_state to inherit shared counters.
        for parent in range(ilvl):
            if parent not in counters:
                # First try to inherit from shared abstract state (for numIds sharing abstractNumId)
                if abstract_state is not None and parent in abstract_state:
                    counters[parent] = abstract_state[parent]
                else:
                    # Fall back to pstart only when no shared state exists
                    pinfo = level_map.get(parent, {})
                    pstart = pinfo.get('start', 1)
                    try:
                        counters[parent] = int(pstart) if pstart is not None else 1
                    except (TypeError, ValueError):
                        counters[parent] = 1
            elif abstract_state is not None and parent in abstract_state:
                # Sync stale per-numId parent counter from the shared abstract
                # state.  Another numId (sharing the same abstractNumId) may
                # have advanced the parent counter since our last use.
                counters[parent] = abstract_state[parent]
            if abstract_state is not None:
                abstract_state[parent] = counters[parent]

        # Increment current level
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

        rendered = self._render_level_text(num_id, ilvl, counters)
        if not rendered:
            rendered = self._format_value(counters.get(ilvl), str(level_info.get('numFmt')))

        suffix = str(level_info.get('suffix') or '').lower()
        if suffix in {'space', 'tab'}:
            return f"{rendered} "
        if suffix == 'nothing':
            return str(rendered)
        return str(rendered)

class DocxParser:
    """Parse DOCX files directly from XML without python-docx."""

    def __init__(
        self,
        get_table_content: bool = True,
        get_image_content: bool = True,
        get_shape_content: bool = True,
        keep_strikethrough_text: bool = False,
    ):
        self.get_table_content = get_table_content
        self.get_image_content = get_image_content
        self.get_shape_content = get_shape_content
        self.keep_strikethrough_text = keep_strikethrough_text
        self._numbering_helper: Optional[NumberingHelper] = None
        self._strike_style_ids: Set[str] = set()
        self._style_to_heading_level: Dict[str, int] = {}
        # Style → (numId, ilvl) mapping for styles that have numbering defined
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

        self.gray_brightness_thr = 180.0
        self.gray_spread_thr = 12

        self._theme_resolver = ThemeResolver(None)
        self._table_style_helper = None

        # Cache: rel_id -> (saved_path, full_md5)
        self._image_cache_by_rid: Dict[str, Tuple[str, str]] = {}

        # Cache: full_md5 -> saved_path (dedupe across different rel_ids with same bytes)
        self._image_cache_by_hash: Dict[str, str] = {}


    def extract_docx_text(
        self,
        docx_path: str,
        output_dir: Optional[str] = None,
    ) -> List[dict]:
        """
        Extract content from a DOCX file.
        
        Returns a hierarchical tree structure with headings and content.
        """
        try:
            with zipfile.ZipFile(docx_path, 'r') as docx_zip:
                document_xml = docx_zip.read("word/document.xml")
                
                numbering_xml = None
                try:
                    numbering_xml = docx_zip.read("word/numbering.xml")
                except KeyError:
                    pass

                styles_xml = None
                try:
                    styles_xml = docx_zip.read("word/styles.xml")
                except KeyError:
                    pass

                theme1_xml = None
                try:
                    theme1_xml = docx_zip.read("word/theme/theme1.xml")
                except KeyError:
                    pass

                rels = {}
                try:
                    rels_xml = docx_zip.read("word/_rels/document.xml.rels")
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

                # Parse document
                tree = self._parse_document(document_xml, docx_zip, rels, output_dir)

                return tree

        except Exception as e:
            log.error(f"Failed to parse DOCX: {e}")
            raise

    def _parse_relationships(self, rels_xml: bytes) -> Dict[str, str]:
        """Parse relationship IDs to targets."""
        rels = {}
        try:
            root = etree.fromstring(rels_xml)
            for rel in root.findall(ns("http://schemas.openxmlformats.org/package/2006/relationships", "Relationship")):
                rel_id = rel.get("Id")
                target = rel.get("Target")
                if rel_id and target:
                    rels[rel_id] = target
        except Exception as e:
            log.warning(f"Failed to parse relationships: {e}")
        return rels

    def _parse_styles(self, styles_xml: bytes) -> None:
        """Parse styles.xml to extract heading levels, strikethrough styles, numPr definitions, and ToC styles."""
        # ---- heading resolution metadata (paragraph styles) ----
        style_name_map: Dict[str, str] = {}
        style_alias_map: Dict[str, str] = {}
        style_based_on: Dict[str, str] = {}
        style_outline_lvl: Dict[str, int] = {}
        try:
            root = etree.fromstring(styles_xml)
            for style in root.findall(ns(W_NS, "style")):
                style_id = style.get(ns(W_NS, "styleId"))
                if not style_id:
                    continue
                
                # 1. Extract heading level and ToC indicator from style name
                name_el = style.find(ns(W_NS, "name"))
                if name_el is not None:
                    name_val = name_el.get(ns(W_NS, "val"))
                    if name_val:
                        # Match "heading 1", "heading 2", etc. (case-insensitive)
                        # match = re.match(r"heading\s*(\d+)", name_val, re.IGNORECASE)
                        # if match:
                        #     self._style_to_heading_level[style_id] = int(match.group(1))
                        
                        # Match ToC styles: "toc 1", "toc 2", "TOC1", etc. (case-insensitive)
                        toc_match = re.match(r"toc\s*\d+", name_val, re.IGNORECASE)
                        if toc_match:
                            self._style_to_toc.add(style_id)
                
                # 1) Collect paragraph-style metadata for robust heading detection
                #    We will resolve heading levels AFTER the loop using:
                #    - w:outlineLvl (strong)
                #    - styleId HeadingN (strong)
                #    - basedOn inheritance (strong)
                #    - name/aliases regex (fallback)
                style_type = style.get(ns(W_NS, "type"))
                if style_type == "paragraph":
                    # name
                    name_el = style.find(ns(W_NS, "name"))
                    if name_el is not None:
                        name_val = name_el.get(ns(W_NS, "val"))
                        if name_val:
                            style_name_map[style_id] = name_val

                    # aliases (comma-separated display aliases)
                    aliases_el = style.find(ns(W_NS, "aliases"))
                    if aliases_el is not None:
                        aliases_val = aliases_el.get(ns(W_NS, "val"))
                        if aliases_val:
                            style_alias_map[style_id] = aliases_val

                    # basedOn
                    based_el = style.find(ns(W_NS, "basedOn"))
                    if based_el is not None:
                        base_id = based_el.get(ns(W_NS, "val"))
                        if base_id:
                            style_based_on[style_id] = base_id

                    # outlineLvl inside the style's pPr
                    ppr_local = style.find(ns(W_NS, "pPr"))
                    if ppr_local is not None:
                        out = ppr_local.find(ns(W_NS, "outlineLvl"))
                        if out is not None:
                            v = out.get(ns(W_NS, "val"))
                            if v is not None:
                                try:
                                    oi = int(v)
                                    # 0..8 => heading levels 1..9; 9 => no outline level
                                    if 0 <= oi <= 8:
                                        style_outline_lvl[style_id] = oi
                                except ValueError:
                                    pass
                
                # 2. Check if style has strike (only in direct rPr, NOT inside rPrChange)
                # Using descendant search ".//{strike}" would incorrectly match strike
                # inside rPrChange (revision tracking history of old formatting).
                style_rpr = style.find(ns(W_NS, "rPr"))
                if style_rpr is not None:
                    # Check direct children only, skip rPrChange descendants
                    has_strike = (
                        style_rpr.find(ns(W_NS, "strike")) is not None or
                        style_rpr.find(ns(W_NS, "dstrike")) is not None
                    )
                    if has_strike:
                        self._strike_style_ids.add(style_id)
                
                # 3. Extract numPr from style's pPr (for heading auto-numbering)
                ppr = style.find(ns(W_NS, "pPr"))
                if ppr is not None:
                    numpr = ppr.find(ns(W_NS, "numPr"))
                    if numpr is not None:
                        num_id_el = numpr.find(ns(W_NS, "numId"))
                        ilvl_el = numpr.find(ns(W_NS, "ilvl"))
                        if num_id_el is not None:
                            num_id = num_id_el.get(ns(W_NS, "val"))
                            # ilvl defaults to 0 if not specified
                            ilvl = 0
                            if ilvl_el is not None:
                                ilvl_val = ilvl_el.get(ns(W_NS, "val"))
                                if ilvl_val:
                                    try:
                                        ilvl = int(ilvl_val)
                                    except ValueError:
                                        pass
                            if num_id:
                                self._style_to_numpr[style_id] = (num_id, ilvl)
            # ---- Resolve heading levels for paragraph styles ----
            # Priority:
            # 1) style pPr/outlineLvl
            # 2) styleId pattern HeadingN
            # 3) basedOn chain
            # 4) name/aliases fallback (supports EN + JP keyword "見出し")
            heading_id_pat = re.compile(r"^Heading\s*([1-9])$", re.IGNORECASE)
            heading_name_pat = re.compile(r"(heading|見出し)\s*([1-9])", re.IGNORECASE)

            def _resolve_heading_level(sid: str, visiting: Set[str]) -> Optional[int]:
                if not sid:
                    return None
                if sid in self._style_to_heading_level:
                    return self._style_to_heading_level[sid]
                if sid in visiting:
                    return None
                visiting.add(sid)

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
                    lvl = _resolve_heading_level(base, visiting)
                    if lvl is not None:
                        return lvl

                # (4) fallback: name / aliases contains "heading N" or "見出し N"
                nm = style_name_map.get(sid, "")
                al = style_alias_map.get(sid, "")
                blob = f"{nm} {al}".strip()
                m2 = heading_name_pat.search(blob)
                if m2:
                    try:
                        return int(m2.group(2))
                    except ValueError:
                        return None

                return None

            # resolve for all collected paragraph styles
            all_para_style_ids = set(style_name_map.keys()) | set(style_based_on.keys()) | set(style_outline_lvl.keys())
            for sid in all_para_style_ids:
                lvl = _resolve_heading_level(sid, set())
                if lvl is not None:
                    self._style_to_heading_level[sid] = lvl
                    
        except Exception as e:
            log.warning(f"Failed to parse styles: {e}")

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
        
        # Reset heading counters for second pass
        self._heading_counters = [0] * 9

        body = root.find(ns(W_NS, "body"))
        if body is None:
            return []

        stack = []  # (level, node_dict)
        tree = []

        children = list(body)
        
        # Find the index where main content starts (after ToC and front matter)
        start_index = self._find_content_start_index(children)
        
        i = start_index

        # Buffer consecutive drawing-only paragraphs so we can decide "picture cluster"
        # BEFORE emitting any shape text (prevents early labels like ライセンスキー/車載機).
        pending_drawing_ps: List = []

        def flush_pending_drawing_ps():
            nonlocal pending_drawing_ps
            if not pending_drawing_ps:
                return

            has_img = any(self._paragraph_has_image(p) for p in pending_drawing_ps)

            # Count paragraphs that actually contain drawings (not just spacers)
            drawing_count = sum(
                1 for p in pending_drawing_ps if self._is_drawing_only_paragraph(p)
            )

            # Case 1: picture/diagram cluster => extract images, substantial
            # shape text, and caption-like shape text.
            # Triggered when cluster has raster images OR many vector shapes (≥3 drawing
            # paragraphs indicates a diagram/flowchart).
            if has_img or drawing_count >= 3:
                if stack:
                    node = stack[-1][1]
                    for p in pending_drawing_ps:
                        # 1) Extract actual images (blips) and emit IMAGE_PATH markers
                        img_placeholders = self._extract_images_from_paragraph(p)
                        for img_ph in img_placeholders:
                            if "content" not in node:
                                node["content"] = img_ph
                            else:
                                node["content"] += "\n" + img_ph

                        # 2) Extract substantial bordered-shape text
                        #    (e.g. annotation rectangles with multi-line content)
                        shape_texts = self._extract_substantial_shape_text_from_paragraph(p)
                        for st in shape_texts:
                            block = f"{SHAPE_CONTENT_START_MARKER} {st} {SHAPE_CONTENT_END_MARKER}"
                            if "content" not in node:
                                node["content"] = block
                            else:
                                node["content"] += "\n" + block

                        # 3) Keep caption-like shape text (existing behaviour)
                        cap = self._extract_caption_text_from_paragraph(p)
                        if cap:
                            block = f"{SHAPE_CONTENT_START_MARKER} {cap} {SHAPE_CONTENT_END_MARKER}"
                            if "content" not in node:
                                node["content"] = block
                            else:
                                node["content"] += "\n" + block

                        if "content" in node:
                            node["content"] = self._merge_ver_marker(node["content"])
                pending_drawing_ps = []
                return

            # Case 2: not a picture cluster => emit normally (standalone shapes preserved)
            for p in pending_drawing_ps:
                text, _, _ = self._parse_paragraph(p)
                if stack and text:
                    if "content" not in stack[-1][1]:
                        stack[-1][1]["content"] = text
                    else:
                        stack[-1][1]["content"] += "\n" + text
                    stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])

            pending_drawing_ps = []

        while i < len(children):
            child = children[i]

            if child.tag == ns(W_NS, "p"):

                # If drawing-only => buffer it, do NOT emit yet
                if self._is_drawing_only_paragraph(child):
                    pending_drawing_ps.append(child)
                    i += 1
                    continue

                # If we already have pending drawing paragraphs and this paragraph is effectively empty, treat it as a spacer within the same diagram cluster (don't break the buffer).
                if pending_drawing_ps and self._is_effectively_empty_paragraph(child):
                    pending_drawing_ps.append(child)
                    i += 1
                    continue

                # 2) Non drawing-only => flush buffered block first
                flush_pending_drawing_ps()

                # 3) Normal paragraph handling
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
                    if "content" not in stack[-1][1]:
                        stack[-1][1]["content"] = text
                    else:
                        stack[-1][1]["content"] += "\n" + text
                    stack[-1][1]["content"] = self._merge_ver_marker(stack[-1][1]["content"])

                i += 1
                continue

            if child.tag == ns(W_NS, "tbl"):
                # Flush before table so buffered diagram doesn't leak past table boundary
                flush_pending_drawing_ps()

                md_blocks, consumed = self._parse_table_chain(children, i)
                for table_md in md_blocks:
                    block = (
                        f"\n[START_TABLE_CONTENT] {table_md} [END_TABLE_CONTENT]\n"
                        if self.get_table_content
                        else "\n[START_TABLE_CONTENT] TABLE [END_TABLE_CONTENT]\n"
                    )
                    if stack:
                        node = stack[-1][1]
                        if "content" not in node:
                            node["content"] = block
                        else:
                            node["content"] += "\n" + block
                        node["content"] = self._merge_ver_marker(node["content"])
                i += max(1, consumed)
                continue

            # Other elements: flush pending and move on
            flush_pending_drawing_ps()
            i += 1

        # End of body: flush remaining buffered drawing paragraphs
        flush_pending_drawing_ps()

        # Prune empty nodes
        return self._prune_tree(tree)

    def _merge_ver_marker(self, text: str) -> str:
        """Remove a newline directly before the ▲Ver marker to keep text contiguous."""
        if not text:
            return text
        return text.replace("\n▲Ver", "▲Ver")\
                    .replace("(\n", "(")\
                    .replace("~~~~", "")\
                    .replace("~~ ~~", " ")

    def _normalize_text_for_matching(self, text: str) -> str:
        """
        Normalize text for matching between ToC entries and body headings.
        Removes numbering prefix, extra whitespace, and normalizes unicode.
        """
        if not text:
            return ""
        # Handles cases with or without space after numbering
        normalized = re.sub(r'^[\d.]+[\s　]*', '', text)
        # Remove tabs and normalize whitespace
        normalized = re.sub(r'[\t　]+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove page numbers at the end (ToC often has page numbers)
        normalized = re.sub(r'\d+$', '', normalized)
        return normalized.strip()
    
    @staticmethod
    def _normalize_table_cell_text(cell_text: str) -> str:
        """Replace newlines inside a table cell following the requested rules."""
        if not cell_text:
            return ""

        result: List[str] = []
        last_non_space: Optional[str] = None

        for char in cell_text:
            if char != "\n":
                # Collapse consecutive spaces to avoid duplicates when we inject our own.
                if char == " " and result and result[-1] == " ":
                    continue
                result.append(char)
                if not char.isspace():
                    last_non_space = char
                continue

            # Remove trailing whitespace before deciding which separator to inject.
            while result and result[-1].isspace():
                result.pop()

            if not last_non_space:
                continue

            replacement = " " if last_non_space == "." else ". "
            for repl_char in replacement:
                if repl_char == " " and result and result[-1] == " ":
                    continue
                result.append(repl_char)
                if not repl_char.isspace():
                    last_non_space = repl_char

        return "".join(result).strip()

    def _extract_toc_entries(self, root) -> None:
        """
        Extract Table of Contents entries to build numbering ground truth.
        ToC entries typically have styles like TOC1, TOC2, TOC3, etc.
        """
        self._toc_numbering_map = {}
        self._has_toc = False
        
        body = root.find(ns(W_NS, "body"))
        if body is None:
            return
        
        toc_pattern = re.compile(r'^TOC(\d+)$', re.IGNORECASE)
        # Match numbering at start: "1.2.3" followed by optional space then non-digit
        # Also handles "1.2.3Text" (no space) by looking for transition to non-digit
        numbering_pattern = re.compile(r'^(\d+(?:\.\d+)*)[\s　]*(?=[^\d\s.]|$)')
        
        for p_elem in body.findall(ns(W_NS, "p")):
            ppr = p_elem.find(ns(W_NS, "pPr"))
            if ppr is None:
                continue
            
            pstyle = ppr.find(ns(W_NS, "pStyle"))
            if pstyle is None:
                continue
            
            style_val = pstyle.get(ns(W_NS, "val"), "")
            toc_match = toc_pattern.match(style_val)
            if not toc_match:
                continue
            
            # This is a ToC entry
            self._has_toc = True
            
            # Extract text from this paragraph
            text_parts = []
            for r in p_elem.findall(ns(W_NS, "r")):
                for t in r.findall(ns(W_NS, "t")):
                    if t.text:
                        text_parts.append(t.text)
            
            full_text = "".join(text_parts).strip()
            if not full_text:
                continue
            
            # Extract numbering from the beginning of the ToC text
            num_match = numbering_pattern.match(full_text)
            if num_match:
                numbering = num_match.group(1).rstrip('.')
                # Get the text without numbering for matching
                text_without_num = full_text[num_match.end():].strip()
                normalized_text = self._normalize_text_for_matching(text_without_num)
                
                if normalized_text:
                    self._toc_numbering_map[normalized_text] = numbering
        
        if self._has_toc:
            log.debug(f"Found ToC with {len(self._toc_numbering_map)} numbered entries")

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
        if not children:
            return 0
        
        toc_end_index = -1
        front_matter_end_index = -1
        
        # Keywords that indicate front matter headings (case-insensitive)
        front_matter_keywords = [
            # English
            "revision history", "change history", "change log", "version history",
            "document history", "table of contents", "contents",
            # Japanese
            "変更履歴", "改訂履歴", "目次",
            # Mixed
            "revision", "toc",
        ]
        
        toc_style_id_pattern = re.compile(r'^TOC\d+$', re.IGNORECASE)
        
        def is_toc_style(style_id: str) -> bool:
            """Check if a style ID represents a ToC style."""
            if not style_id:
                return False
            # Direct match on ID pattern
            if toc_style_id_pattern.match(style_id):
                return True
            # Check if this style ID maps to a ToC-named style
            # (for cases where style ID is numeric like "10" but name is "toc 1")
            if style_id in self._style_to_toc:
                return True
            return False
        
        for i, child in enumerate(children):
            tag = etree.QName(child).localname
            
            # Method 1: Detect w:sdt (Structured Document Tag) for ToC
            # This is the most reliable method - Word uses sdt for auto-generated ToC
            if tag == "sdt":
                sdtpr = child.find(ns(W_NS, "sdtPr"))
                if sdtpr is not None:
                    # Check docPartObj/docPartGallery for "Table of Contents"
                    doc_part_obj = sdtpr.find(ns(W_NS, "docPartObj"))
                    if doc_part_obj is not None:
                        gallery = doc_part_obj.find(ns(W_NS, "docPartGallery"))
                        if gallery is not None:
                            gallery_val = (gallery.get(ns(W_NS, "val")) or "").lower()
                            if "contents" in gallery_val or "toc" in gallery_val:
                                toc_end_index = i
                                log.debug(f"Found ToC sdt at index {i}")
                continue
            
            # Method 2: Detect paragraphs with TOC styles (TOC1, TOC2, etc.)
            # These appear inside or after ToC sdt element
            if tag == "p":
                ppr = child.find(ns(W_NS, "pPr"))
                if ppr is not None:
                    pstyle = ppr.find(ns(W_NS, "pStyle"))
                    if pstyle is not None:
                        style_val = pstyle.get(ns(W_NS, "val"), "")
                        if is_toc_style(style_val):
                            toc_end_index = i
                            continue
                
                # Method 3: Semantic detection for front matter headings
                # Only check headings (paragraphs with heading styles)
                heading_level = None
                if ppr is not None:
                    pstyle = ppr.find(ns(W_NS, "pStyle"))
                    if pstyle is not None:
                        style_val = pstyle.get(ns(W_NS, "val"), "")
                        if style_val in self._style_to_heading_level:
                            heading_level = self._style_to_heading_level[style_val]
                    
                    # Also check outlineLvl
                    if heading_level is None:
                        outline_lvl = ppr.find(ns(W_NS, "outlineLvl"))
                        if outline_lvl is not None:
                            val = outline_lvl.get(ns(W_NS, "val"))
                            if val is not None:
                                try:
                                    heading_level = int(val) + 1
                                except ValueError:
                                    pass
                
                if heading_level is not None:
                    # Extract text from paragraph
                    text_parts = []
                    for r in child.findall(f".//{ns(W_NS, 'r')}"):
                        for t in r.findall(ns(W_NS, "t")):
                            if t.text:
                                text_parts.append(t.text)
                    full_text = "".join(text_parts).strip().lower()
                    
                    # Check if this heading matches front matter keywords
                    # Only skip if:
                    # 1. It's before or at toc_end_index, OR
                    # 2. We haven't found a ToC yet and this looks like front matter
                    is_front_matter = False
                    for keyword in front_matter_keywords:
                        if keyword in full_text:
                            is_front_matter = True
                            break
                    
                    if is_front_matter:
                        # Only treat as front matter if we're still in the early part of doc
                        # or if we already detected a ToC
                        if toc_end_index >= 0 or i < 20:  # Be conservative
                            front_matter_end_index = i
                            log.debug(f"Found front matter heading at index {i}: {full_text[:50]}")
                    else:
                        # This is a real content heading
                        # If we've passed the ToC or front matter, this is where content starts
                        if toc_end_index >= 0 or front_matter_end_index >= 0:
                            # We found ToC/front matter and now found real content
                            start_idx = max(toc_end_index, front_matter_end_index) + 1
                            # Skip any empty paragraphs after ToC
                            while start_idx < len(children):
                                elem = children[start_idx]
                                if etree.QName(elem).localname == "p":
                                    txt = self._get_paragraph_text(elem)
                                    if txt.strip():
                                        break
                                elif etree.QName(elem).localname in ("tbl", "sdt"):
                                    break
                                start_idx += 1
                            log.debug(f"Content starts at index {start_idx}")
                            return start_idx
        
        # If we found ToC but didn't find content heading after it, start after the ToC
        if toc_end_index >= 0:
            start_idx = toc_end_index + 1
            # Skip empty paragraphs
            while start_idx < len(children):
                elem = children[start_idx]
                if etree.QName(elem).localname == "p":
                    txt = self._get_paragraph_text(elem)
                    if txt.strip():
                        break
                elif etree.QName(elem).localname in ("tbl", "sdt"):
                    break
                start_idx += 1
            return start_idx
        
        # No ToC or front matter detected
        return 0
    
    def _get_paragraph_text(self, p_elem) -> str:
        """Quick helper to get raw text from a paragraph without side effects."""
        text_parts = []
        for r in p_elem.findall(f".//{ns(W_NS, 'r')}"):
            for t in r.findall(ns(W_NS, "t")):
                if t.text:
                    text_parts.append(t.text)
        return "".join(text_parts)

    def _parse_paragraph(
        self, p_elem, *, skip_numbering: bool = False
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
        
        # Skip paragraphs that are inside txbxContent (diagram/shape text boxes)
        # These are editable text inside shapes and should not be parsed as document content
        parent = p_elem.getparent()
        while parent is not None:
            if parent.tag == ns(W_NS, "txbxContent"):
                return "", None, None
            parent = parent.getparent()

        # # Skip entirely-deleted paragraphs.
        # # A paragraph is considered deleted if:
        # #   1. It has w:rsidDel attribute on the <w:p> element, OR
        # #   2. Its pPr/rPr contains <w:del> (paragraph-level deletion marker)
        # # These are paragraphs that have been deleted via tracked changes and
        # # should not appear in the parsed output.
        # rsid_del = p_elem.get(ns(W_NS, "rsidDel"))
        # if rsid_del:
        #     return "", None, None
        # ppr_check = p_elem.find(ns(W_NS, "pPr"))
        # if ppr_check is not None:
        #     rpr_check = ppr_check.find(ns(W_NS, "rPr"))
        #     if rpr_check is not None:
        #         if rpr_check.find(ns(W_NS, "del")) is not None:
        #             return "", None, None
        
        # Check for heading style
        heading_level = None
        ppr = p_elem.find(ns(W_NS, "pPr"))
        
        if ppr is not None:
            pstyle = ppr.find(ns(W_NS, "pStyle"))
            if pstyle is not None:
                style_val = pstyle.get(ns(W_NS, "val"))
                if style_val:
                    # Use our pre-built style-to-heading mapping
                    if style_val in self._style_to_heading_level:
                        heading_level = self._style_to_heading_level[style_val]
            
            # Fallback: check outlineLvl attribute (0-based, so add 1)
            if heading_level is None:
                outline_lvl = ppr.find(ns(W_NS, "outlineLvl"))
                if outline_lvl is not None:
                    val = outline_lvl.get(ns(W_NS, "val"))
                    if val is not None:
                        try:
                            heading_level = int(val) + 1
                        except ValueError:
                            pass

        para_has_image = self._paragraph_has_image(p_elem)

        # Also detect floating (anchor-based) drawings outside textbox content.
        # Only treat an anchor as a floating-image overlay if it
        # actually contains raster image content (a:blip / pic:pic / v:imagedata).
        # Anchors with only shapes/groups (e.g. wpg:wgp diagrams) are content-
        # bearing and their shape text must be extracted normally.
        para_has_floating_drawing = False
        if not para_has_image:
            for _anchor in p_elem.findall(f".//{ns(WP_NS, 'anchor')}"):
                _par = _anchor.getparent()
                _inside_txbx = False
                while _par is not None and _par != p_elem:
                    if _par.tag == ns(W_NS, "txbxContent"):
                        _inside_txbx = True
                        break
                    _par = _par.getparent()
                if not _inside_txbx:
                    # Only suppress shape extraction if anchor has actual image data
                    _has_img = (
                        _anchor.find(f".//{ns(A_NS, 'blip')}") is not None
                        or _anchor.find(f".//{ns(PIC_NS, 'pic')}") is not None
                        or _anchor.find(f".//{ns(V_NS, 'imagedata')}") is not None
                    )
                    if _has_img:
                        para_has_floating_drawing = True
                        break

        para_struck = False
        if ppr is not None:
            # p_rpr = ppr.find(ns(W_NS, "rPr"))
            # if p_rpr is not None:
            #     if (p_rpr.find(ns(W_NS, "strike")) is not None or
            #             p_rpr.find(ns(W_NS, "dstrike")) is not None):
            #         para_struck = True

            # Also treat "strike" table/paragraph styles as struck
            pstyle = ppr.find(ns(W_NS, "pStyle"))
            if pstyle is not None:
                style_val = pstyle.get(ns(W_NS, "val"))
                if style_val and style_val in self._strike_style_ids:
                    para_struck = True


        # Extract text from runs (including those inside w:ins tracked insertions)
        # Use descendant search to capture runs nested in w:ins, w:hyperlink, etc.
        # But skip runs inside w:del (tracked deletions) or w:txbxContent (diagram/shape text boxes)
        text_parts = []

        # Field tracking: skip cached results of REF, STYLEREF, SEQ fields
        # These fields produce auto-generated text that may be stale/incorrect.
        _field_stack: List[dict] = []  # stack of {"instr": str, "in_result": bool, "skip": bool}

        for r in p_elem.findall(f".//{ns(W_NS, 'r')}"):
            # Skip runs that are inside a w:del (deletion) or w:txbxContent (shape text box).
            # Walk up the tree to check if any ancestor is w:del or w:txbxContent.
            parent = r.getparent()
            skip = False
            while parent is not None and parent != p_elem:
                if parent.tag == ns(W_NS, "txbxContent"):
                    skip = True
                    break

                # Keep skipping deleted content in normal paragraphs,
                # but allow it in headings to avoid truncation like "...項目items"
                if parent.tag == ns(W_NS, "del") and heading_level is None:
                    skip = True
                    break
                parent = parent.getparent()
            
            if skip:
                continue

            # --- Field character tracking (REF / STYLEREF / SEQ) ---
            fld_char = r.find(ns(W_NS, "fldChar"))
            if fld_char is not None:
                fld_type = fld_char.get(ns(W_NS, "fldCharType")) or ""
                if fld_type == "begin":
                    _field_stack.append({"instr": "", "in_result": False, "skip": False})
                elif fld_type == "separate" and _field_stack:
                    _field_stack[-1]["in_result"] = True
                elif fld_type == "end" and _field_stack:
                    _field_stack.pop()

            # Accumulate field instruction text
            instr_el = r.find(ns(W_NS, "instrText"))
            if instr_el is not None and instr_el.text and _field_stack:
                _field_stack[-1]["instr"] += instr_el.text
                instr = _field_stack[-1]["instr"].strip()
                if instr.startswith(("REF ", "STYLEREF ", "SEQ ")):
                    _field_stack[-1]["skip"] = True

            # If we are inside the result region of a field we want to skip, drop this run
            if any(f["in_result"] and f["skip"] for f in _field_stack):
                continue

            run_text = self._parse_run(r, paragraph_has_image=para_has_image or para_has_floating_drawing, paragraph_struck=para_struck)

            if run_text:
                text_parts.append(run_text)

        full_text = "".join(text_parts).strip()

        if heading_level is None and not full_text:
            return "", None, None

        # Check for numbering from multiple sources (in priority order)
        num_id = None
        ilvl = None
        
        # Priority 1: Check paragraph's explicit numPr
        if ppr is not None:
            num_pr = ppr.find(ns(W_NS, "numPr"))
            if num_pr is not None:
                num_id_el = num_pr.find(ns(W_NS, "numId"))
                ilvl_el = num_pr.find(ns(W_NS, "ilvl"))
                if num_id_el is not None:
                    num_id = num_id_el.get(ns(W_NS, "val"))
                if ilvl_el is not None:
                    ilvl = ilvl_el.get(ns(W_NS, "val"))
        
        # Priority 2: If paragraph has no numPr, check the style's numPr
        if (num_id is None or ilvl is None) and ppr is not None:
            pstyle = ppr.find(ns(W_NS, "pStyle"))
            if pstyle is not None:
                style_val = pstyle.get(ns(W_NS, "val"))
                if style_val and style_val in self._style_to_numpr:
                    style_num_id, style_ilvl = self._style_to_numpr[style_val]
                    if num_id is None:
                        num_id = style_num_id
                    if ilvl is None:
                        ilvl = str(style_ilvl)
        
        # Apply numbering if we have valid numId and ilvl
        # Skip numbering when called from utility functions to avoid counter side effects
        if num_id and ilvl and self._numbering_helper and not skip_numbering:
            try:
                # For headings, we must not advance counters if we decide to ignore an invalid marker (e.g., unresolved %N). Otherwise later headings become off-by-one.
                helper = self._numbering_helper
                abstract_id = helper.num_to_abstract.get(num_id)  # type: ignore[attr-defined]
                if abstract_id:
                    counters_ref = helper.abstract_counters[abstract_id]  # type: ignore[attr-defined]
                else:
                    counters_ref = helper.counters[num_id]  # type: ignore[attr-defined]
                snapshot = dict(counters_ref)

                marker = helper.get_marker(num_id, int(ilvl))
                if marker:
                    # For headings: skip bullet markers or markers with unresolved placeholders
                    is_valid_heading_marker = True
                    if heading_level:
                        if marker == '•' or marker.startswith('•'):
                            is_valid_heading_marker = False
                        elif '%' in marker:
                            is_valid_heading_marker = False

                    if heading_level and not is_valid_heading_marker:
                        # Roll back numbering state so this paragraph doesn't affect later headings.
                        counters_ref.clear()
                        counters_ref.update(snapshot)
                    else:
                        full_text = f"{marker} {full_text}" if full_text else str(marker)
            except Exception as e:
                log.debug(f"Failed to get marker: {e}")
                
        # We only parse numbering that exists in the document itself (via numPr or in text)
        heading_text = full_text if heading_level else None

        # Demote headings whose remaining text is just a version/change marker
        # (e.g. "▲3.00", "-3.00").  These are artifacts of struck-through
        # heading content and should become regular content instead.
        if heading_level and heading_text:
            _ht = heading_text.strip()
            if re.match(r'^[▲▽△▼]?\s*-?\s*\d+\.\d+\s*$', _ht):
                heading_level = None
                heading_text = None

        return full_text, heading_level, heading_text
    
    def _paragraph_has_image(self, p_elem) -> bool:
        """
        True if this paragraph contains an actual image (a:blip / pic:pic / v:imagedata),
        excluding anything inside w:txbxContent.
        """
        if p_elem is None or p_elem.tag != ns(W_NS, "p"):
            return False

        # Look through drawings in this paragraph
        for drawing in p_elem.findall(f".//{ns(W_NS, 'drawing')}"):
            # Skip drawings inside textboxes (shape content)
            parent = drawing.getparent()
            while parent is not None and parent != p_elem:
                if parent.tag == ns(W_NS, "txbxContent"):
                    drawing = None
                    break
                parent = parent.getparent()
            if drawing is None:
                continue
            if drawing.find(f".//{ns(A_NS, 'blip')}") is not None:
                return True
            if drawing.find(f".//{ns(PIC_NS, 'pic')}") is not None:
                return True
            if drawing.find(f".//{ns(V_NS, 'imagedata')}") is not None:
                return True

        return False

    def _parse_run(
        self,
        r_elem,
        *,
        paragraph_has_image: bool = False,
        paragraph_struck: bool = False,
    ) -> str:
        """Parse a run element and extract text, images, and shapes."""

        # detect run-level strike first
        run_struck = False
        rpr = r_elem.find(ns(W_NS, "rPr"))
        if rpr is not None:
            if (rpr.find(ns(W_NS, "strike")) is not None or
                    rpr.find(ns(W_NS, "dstrike")) is not None):
                run_struck = True

        struck = paragraph_struck or run_struck

        # If struck, drop EVERYTHING in this run (including images), so deprecated figures/captions won't leak images.
        if struck and not self.keep_strikethrough_text:
            return ""

        image_placeholders = self._extract_images_from_element(r_elem)
        shape_placeholders = [] if paragraph_has_image else self._extract_shapes_from_element(r_elem)

        # Otherwise extract visible text (keep original logic)
        text_parts = []
        for child in r_elem:
            local_tag = etree.QName(child).localname
            if local_tag == "t":
                if child.text:
                    text_parts.append(child.text)
            elif local_tag == "delText":
                if child.text:
                    text_parts.append(child.text)
            elif local_tag == "tab":
                text_parts.append(" ")
            elif local_tag == "br":
                text_parts.append("\n")

        text_parts.extend(image_placeholders)
        text_parts.extend(shape_placeholders)
        return "".join(text_parts)
        
    # ---------- Table merge helpers ----------

    def _is_pagebreak_only_paragraph(self, p_elem) -> bool:
        """True if paragraph contains a hard page break and no meaningful text."""
        if p_elem is None or p_elem.tag != ns(W_NS, "p"):
            return False
        for br in p_elem.findall(f".//{ns(W_NS,'br')}"):
            if (br.get(ns(W_NS, "type")) or "").lower() == "page":
                txt, _, _ = self._parse_paragraph(p_elem, skip_numbering=True)
                return txt.strip() == ""
        return False


    def _is_effectively_empty_paragraph(self, p_elem) -> bool:
        """True if paragraph yields no extracted text (bookmarks-only / whitespace-only)."""
        if p_elem is None or p_elem.tag != ns(W_NS, "p"):
            return False
        txt, _, _ = self._parse_paragraph(p_elem, skip_numbering=True)
        return txt.strip() == ""


    def _explicit_header_row_count(self, tbl_elem) -> int:
        """Count contiguous top rows marked as repeating headers via w:tblHeader."""
        if tbl_elem is None or tbl_elem.tag != ns(W_NS, "tbl"):
            return 0
        count = 0
        for tr in tbl_elem.findall(ns(W_NS, "tr")):
            trpr = tr.find(ns(W_NS, "trPr"))
            if trpr is not None and trpr.find(ns(W_NS, "tblHeader")) is not None:
                count += 1
                continue
            break
        return count

    def _table_has_explicit_header_rows(self, tbl_elem) -> bool:
        """Strong signal: table has w:trPr/w:tblHeader repeating header rows."""
        return self._explicit_header_row_count(tbl_elem) > 0


    def _tbllook_firstrow_enabled(self, tbl_elem) -> bool:
        """Best-effort: detect tblLook firstRow flag (attr or bitmask)."""
        tblpr = tbl_elem.find(ns(W_NS, "tblPr")) if tbl_elem is not None else None
        if tblpr is None:
            return False
        tl = tblpr.find(ns(W_NS, "tblLook"))
        if tl is None:
            return False

        # Newer docs: w:firstRow="1"
        first_row = tl.get(ns(W_NS, "firstRow")) or tl.get("firstRow")
        if first_row and str(first_row).lower() in {"1", "true", "on"}:
            return True

        # Older docs: bitmask in w:val; 0x0020 => firstRow
        val = tl.get(ns(W_NS, "val")) or tl.get("val")
        if val:
            try:
                mask = int(str(val), 16)
                return (mask & 0x0020) != 0
            except ValueError:
                return False
        return False


    def _tbl_firstrow_cnf_hint(self, tbl_elem) -> bool:
        """Best-effort: detect cnfStyle firstRow on the first row/cell."""
        tr = tbl_elem.find(ns(W_NS, "tr")) if tbl_elem is not None else None
        if tr is None:
            return False
        tcs = tr.findall(ns(W_NS, "tc"))
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
            if node.tag == ns(W_NS, "tbl"):
                return j, sep
            if node.tag == ns(W_NS, "p"):
                if self._is_effectively_empty_paragraph(node) or self._is_pagebreak_only_paragraph(node):
                    sep.append(j)
                    j += 1
                    continue
                return None, None
            return None, None
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
        assert children[start_idx].tag == ns(W_NS, "tbl")
        tbl0 = children[start_idx]
        cols0 = self._tbl_col_count(tbl0)

        group_rows = self._table_to_grid(tbl0)
        group_sig = self._header_signature(tbl0, group_rows)
        group_first_tbl = tbl0

        consumed_end = start_idx + 1

        while True:
            nxt_idx, sep_idx = self._scan_next_table_candidate(children, consumed_end - 1)
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

        return md_blocks, (consumed_end - start_idx)

    def _tbl_col_count(self, tbl_elem) -> int:
        """
        Determine table column count (grid width).
        Prefer w:tblGrid/w:gridCol. Fallback to inferred colspans if missing.
        """
        tbl_grid = tbl_elem.find(ns(W_NS, "tblGrid"))
        if tbl_grid is not None:
            cols = tbl_grid.findall(ns(W_NS, "gridCol"))
            if cols:
                return len(cols)

        # Fallback: infer from rows by summing gridSpans (best effort)
        max_cols = 0
        for tr in tbl_elem.findall(ns(W_NS, "tr")):
            cnt = self._row_grid_before(tr)
            for tc in tr.findall(ns(W_NS, "tc")):
                cnt += self._tc_grid_span(tc)
            max_cols = max(max_cols, cnt)
        return max_cols

    def _row_grid_before(self, tr_elem) -> int:
        """
        Row-level offset before first cell (w:trPr/w:gridBefore).
        Often absent; return 0 if not found.
        """
        trpr = tr_elem.find(ns(W_NS, "trPr"))
        if trpr is None:
            return 0
        gb = trpr.find(ns(W_NS, "gridBefore"))
        if gb is None:
            return 0
        val = gb.get(ns(W_NS, "val"))
        try:
            return int(val) if val is not None else 0
        except ValueError:
            return 0

    def _tc_grid_span(self, tc_elem) -> int:
        """Cell horizontal span (w:tcPr/w:gridSpan/@w:val). Default 1."""
        tcpr = tc_elem.find(ns(W_NS, "tcPr"))
        if tcpr is None:
            return 1
        gs = tcpr.find(ns(W_NS, "gridSpan"))
        if gs is None:
            return 1
        val = gs.get(ns(W_NS, "val"))
        try:
            return int(val) if val is not None else 1
        except ValueError:
            return 1

    def _tc_vmerge_state(self, tc_elem) -> str:
        """
        Vertical merge state:
        - "restart" if w:vMerge/@w:val="restart"
        - "continue" if w:vMerge exists with no val or val="continue"
        - "none" if no w:vMerge
        """
        tcpr = tc_elem.find(ns(W_NS, "tcPr"))
        if tcpr is None:
            return "none"
        vm = tcpr.find(ns(W_NS, "vMerge"))
        if vm is None:
            return "none"
        val = vm.get(ns(W_NS, "val"))
        if val is None or val == "" or str(val).lower() == "continue":
            return "continue"
        if str(val).lower() == "restart":
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
        for p in tc_elem.findall(ns(W_NS, "p")):
            txt, _, _ = self._parse_paragraph(p, skip_numbering=False)
            if txt:
                parts.append(txt)
        return "\n".join(parts).strip()

    @staticmethod
    def _is_gray_hex(fill_hex: str, *, brightness_thr: float, spread_thr: int) -> bool:
        if not fill_hex or not re.fullmatch(r"[0-9A-Fa-f]{6}", fill_hex):
            return False
        fill_hex = fill_hex.upper()
        r = int(fill_hex[0:2], 16)
        g = int(fill_hex[2:4], 16)
        b = int(fill_hex[4:6], 16)
        spread = max(r, g, b) - min(r, g, b)
        brightness = (r + g + b) / 3.0
        return (spread <= spread_thr) and (brightness <= brightness_thr)

    def _is_header_cell(self, r_idx: int, tbl_elem, tr_elem, tc_elem, spec: FillSpec) -> bool:
        """
        Decide whether this cell belongs to the table header row.
        Conservative: header if first row index OR cnfStyle firstRow flag OR style firstRow source.
        """
        # Check multiple conditions - return True on first match
        # 0) Explicit repeating header rows: w:trPr/w:tblHeader
        try:
            if r_idx < self._explicit_header_row_count(tbl_elem):
                return True
        except Exception:
            pass
        
        # 1) First physical row
        if r_idx == 0:
            return True

        # 2) cnfStyle firstRow flag from tcPr/trPr
        cnf = self._cnf_attrs(tc_elem, tr_elem)
        if cnf.get("firstRow") in {"1", "true", "on"}:
            return True

        # 3) Style-driven firstRow conditional
        if spec and isinstance(spec.source, str) and spec.source.endswith(":firstRow"):
            return True

        return False

    def _tbl_style_id(self, tbl_elem) -> str:
        tblpr = tbl_elem.find(ns(W_NS, "tblPr"))
        if tblpr is None:
            return ""
        st = tblpr.find(ns(W_NS, "tblStyle"))
        if st is None:
            return ""
        return (st.get(ns(W_NS, "val")) or st.get("val") or "").strip()

    def _cnf_attrs(self, tc_elem, tr_elem) -> Dict[str, str]:
        """
        Extract cnfStyle attributes into a dict {localname: value}.
        We'll try cell cnfStyle first, then row cnfStyle.
        """
        def read_cnf(node, pr_tag: str) -> Dict[str, str]:
            if node is None:
                return {}
            pr = node.find(ns(W_NS, pr_tag))
            if pr is None:
                return {}
            cnf = pr.find(ns(W_NS, "cnfStyle"))
            if cnf is None:
                return {}
            out = {}
            for k, v in cnf.attrib.items():
                out[etree.QName(k).localname] = v
            return out

        out = read_cnf(tc_elem, "tcPr")
        if out:
            return out
        return read_cnf(tr_elem, "trPr")

    def _shd_to_spec(self, shd_el, source: str) -> FillSpec:
        if shd_el is None:
            return FillSpec()
        fill = (shd_el.get(ns(W_NS, "fill")) or shd_el.get("fill") or "").strip().upper()
        theme_fill = (shd_el.get(ns(W_NS, "themeFill")) or shd_el.get("themeFill") or "").strip()
        theme_shade = (shd_el.get(ns(W_NS, "themeFillShade")) or shd_el.get("themeFillShade") or "").strip()
        theme_tint = (shd_el.get(ns(W_NS, "themeFillTint")) or shd_el.get("themeFillTint") or "").strip()
        if fill and not re.fullmatch(r"[0-9A-F]{6}", fill):
            fill = ""
        return FillSpec(fill_hex=fill, theme_fill=theme_fill, theme_shade=theme_shade, theme_tint=theme_tint, source=source)

    def _tc_shd_spec(self, tc_elem) -> FillSpec:
        tcpr = tc_elem.find(ns(W_NS, "tcPr"))
        if tcpr is None:
            return FillSpec()
        shd = tcpr.find(ns(W_NS, "shd"))
        return self._shd_to_spec(shd, source="tcPr")

    def _tr_shd_spec(self, tr_elem) -> FillSpec:
        trpr = tr_elem.find(ns(W_NS, "trPr"))
        if trpr is None:
            return FillSpec()
        shd = trpr.find(ns(W_NS, "shd"))
        return self._shd_to_spec(shd, source="trPr")

    def _effective_fill_spec(self, tbl_elem, tr_elem, tc_elem) -> FillSpec:
        """
        Priority:
        1) tcPr shading
        2) trPr shading
        3) table style shading (conditional via cnfStyle)
        """
        spec = self._tc_shd_spec(tc_elem)
        if spec.fill_hex or spec.theme_fill:
            return spec

        spec = self._tr_shd_spec(tr_elem)
        if spec.fill_hex or spec.theme_fill:
            return spec

        style_id = self._tbl_style_id(tbl_elem)
        if style_id and self._table_style_helper:
            cnf = self._cnf_attrs(tc_elem, tr_elem)
            spec = self._table_style_helper.resolve_spec(style_id, cnf)
            if spec.fill_hex or spec.theme_fill:
                return spec

        return FillSpec()

    def _cell_is_gray(self, tbl_elem, tr_elem, tc_elem) -> Tuple[bool, str, FillSpec]:
        """
        Returns: (is_gray, resolved_hex, spec_used)
        """
        spec = self._effective_fill_spec(tbl_elem, tr_elem, tc_elem)
        resolved = self._theme_resolver.resolve_to_hex(spec) if self._theme_resolver else (spec.fill_hex or "")
        is_gray = self._is_gray_hex(resolved, brightness_thr=self.gray_brightness_thr, spread_thr=self.gray_spread_thr)
        return is_gray, resolved, spec

    def _table_to_grid(self, tbl_elem) -> List[List[str]]:
        """
        Convert a <w:tbl> element into a rectangular grid (rows x cols) of cell texts.

        Core table parser used for Case B/C virtual table merging.
        NOTE: Does NOT modify the XML; only interprets structure (gridSpan + vMerge).
        """
        C = self._tbl_col_count(tbl_elem)
        if C <= 0:
            return []
        rows: List[List[str]] = []
        active_on = [False] * C
        active_text = [""] * C
        active_mask = [False] * C  # True => blank content for that vertical merge region

        tr_elems = tbl_elem.findall(ns(W_NS, "tr"))
        for r_idx, tr in enumerate(tr_elems):
            row = [None] * C  # type: ignore[list-item]
            seen_continue = [False] * C
            started_here = [False] * C
            col = self._row_grid_before(tr)

            tc_elems = tr.findall(ns(W_NS, "tc"))
            for tc in tc_elems:
                colspan = self._tc_grid_span(tc)
                vstate = self._tc_vmerge_state(tc)

                if col >= C:
                    break
                end = min(C, col + max(1, colspan))

                gray, resolved_hex, spec = self._cell_is_gray(tbl_elem, tr, tc)

                # KEEP HEADER CONTENT: override masking for header cells
                if self._is_header_cell(r_idx, tbl_elem, tr, tc, spec):
                    gray = False

                if vstate == "continue":
                    # continuation placeholder: repeat from active state, but apply mask
                    for k in range(col, end):
                        # If this continuation cell is gray, keep region masked going forward
                        if gray:
                            active_mask[k] = True
                        seen_continue[k] = True
                        row[k] = "" if active_mask[k] else (active_text[k] if active_on[k] else "")

                    col = end
                    continue

                raw_text = self._normalize_table_cell_text(self._tc_text(tc))
                final_text = "" if gray else raw_text

                # write across colspan
                for k in range(col, end):
                    row[k] = final_text
                    # overwrite ends any previous active vertical merge in these columns
                    if active_on[k]:
                        active_on[k] = False
                        active_text[k] = ""
                        active_mask[k] = False

                if vstate == "restart":
                    for k in range(col, end):
                        active_on[k] = True
                        active_text[k] = final_text
                        active_mask[k] = gray
                        started_here[k] = True

                col = end

            # Fill remaining slots (implicit continuation of rowspans or empty)
            for c in range(C):
                if row[c] is None:
                    if active_on[c]:
                        row[c] = "" if active_mask[c] else active_text[c]
                        seen_continue[c] = True
                    else:
                        row[c] = ""

            # Close rowspans that did not continue into this row
            for c in range(C):
                if started_here[c]:
                    active_on[c] = True
                elif active_on[c] and not seen_continue[c]:
                    active_on[c] = False
                    active_text[c] = ""
                    active_mask[c] = False

            # keep row if anything non-empty
            if any(str(cell).strip() for cell in row):
                rows.append([str(cell) for cell in row])

        return rows


    def _rows_to_markdown(self, rows: List[List[str]]) -> str:
        """Convert table rows to Markdown format.
        
        Rejects single-row tables (no header/data distinction).
        First row is always treated as header.
        """
        if not rows:
            return ""

        # Reject single-row tables - no meaningful header/data distinction
        if len(rows) < 2:
            return ""

        # Determine column count
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
                pattern = rf"{re.escape(IMAGE_PATH_START_MARKER)}(.*?){re.escape(IMAGE_PATH_END_MARKER)}"
                cell_esc = re.sub(
                    pattern,
                    lambda m: f"{IMAGE_PATH_START_MARKER}" + m.group(1).replace("\\|", "|") + f"{IMAGE_PATH_END_MARKER}",
                    cell_esc,
                    flags=re.DOTALL
                )
                escaped.append(cell_esc)
            md_lines.append("| " + " | ".join(escaped) + " |")
            if i == 0:
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(md_lines)

    def _should_prune_node(self, node: dict) -> bool:
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

        filename = f"img_{len(self._saved_images) + 1}_{image_hash[:8]}.{extension}"
        path = os.path.join(directory, filename)
        try:
            Path(path).write_bytes(image_bytes)
        except Exception as exc:
            log.warning("Unable to write image %s: %s", rel_id, exc)
            return None
        self._saved_images.append(path)
        return path, image_hash


    def _convert_wmf_emf_to_png(self, vector_bytes: bytes, ext: str) -> Optional[bytes]:
        """
        Convert WMF/EMF bytes to PNG bytes.
        Tries: Inkscape → ImageMagick (magick/convert) → LibreOffice
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
            Path(in_path).write_bytes(vector_bytes)

            if inkscape:
                try:
                    subprocess.run(
                        [inkscape, in_path, "--export-type=png", f"--export-filename={out_path}"],
                        check=True,
                        capture_output=True,
                        timeout=30,
                    )
                    if os.path.exists(out_path):
                        return Path(out_path).read_bytes()
                except subprocess.CalledProcessError as e:
                    log.debug("Inkscape conversion failed: %s", e)

            if magick:
                try:
                    cmd = [magick]
                    if "convert" in magick:
                        cmd = [magick]
                    else:
                        cmd = [magick, "convert"]
                    cmd.extend([in_path, out_path])
                    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                    if os.path.exists(out_path):
                        return Path(out_path).read_bytes()
                except subprocess.CalledProcessError as e:
                    log.debug("ImageMagick conversion failed: %s", e)

            if libre:
                try:
                    subprocess.run(
                        [
                            libre,
                            "--headless",
                            "--convert-to",
                            "png",
                            "--outdir",
                            td,
                            in_path,
                        ],
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                    possible_out = os.path.join(td, "in.png")
                    if os.path.exists(possible_out):
                        return Path(possible_out).read_bytes()
                    if os.path.exists(out_path):
                        return Path(out_path).read_bytes()
                except subprocess.CalledProcessError as e:
                    log.debug("LibreOffice conversion failed: %s", e)

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
            target = "word/" + target
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

    def _paragraph_has_visible_text_outside_textbox(self, p_elem) -> bool:
        """
        True if paragraph has any visible text outside w:txbxContent.
        (We treat text inside shapes/textboxes as not 'paragraph text'.)
        """
        if p_elem is None or p_elem.tag != ns(W_NS, "p"):
            return False

        # any w:t / w:delText not inside w:txbxContent counts as visible text
        for t in p_elem.findall(f".//{ns(W_NS,'t')}") + p_elem.findall(f".//{ns(W_NS,'delText')}"):
            parent = t.getparent()
            inside_txbx = False
            while parent is not None and parent != p_elem:
                if parent.tag == ns(W_NS, "txbxContent"):
                    inside_txbx = True
                    break
                parent = parent.getparent()
            if not inside_txbx and (t.text or "").strip():
                return True

        # tabs/br outside textbox also make it non-empty, but rare; keep conservative
        for br in p_elem.findall(f".//{ns(W_NS,'br')}"):
            parent = br.getparent()
            inside_txbx = False
            while parent is not None and parent != p_elem:
                if parent.tag == ns(W_NS, "txbxContent"):
                    inside_txbx = True
                    break
                parent = parent.getparent()
            if not inside_txbx:
                return True

        return False

    def _is_drawing_only_paragraph(self, p_elem) -> bool:
        """
        Paragraph that contains drawings/shapes/picts but has no normal text outside textboxes.
        Used to detect picture/diagram clusters (many w:p are only anchors).
        """
        if p_elem is None or p_elem.tag != ns(W_NS, "p"):
            return False

        has_drawing = (
            p_elem.find(f".//{ns(W_NS,'drawing')}") is not None
            or p_elem.find(f".//{ns(W_NS,'pict')}") is not None
            or p_elem.find(f".//{ns(V_NS,'shape')}") is not None
        )
        if not has_drawing:
            return False

        return not self._paragraph_has_visible_text_outside_textbox(p_elem)

    _CAPTION_PAT = re.compile(
        r"^\s*(?:図|表)\s*[\d.\-]|^\s*(?:figure|fig\.|picture|table)\s*[\d.\-]",
        re.IGNORECASE,
    )

    def _is_caption_text(self, text: str) -> bool:
        if not text:
            return False
        return self._CAPTION_PAT.search(text.strip()) is not None

    # ---------- Structural shape property helpers ----------

    def _wsp_is_diagram_content(self, wsp) -> bool:
        """
        Return True if a wps:wsp shape is a diagram/flowchart element rather
        than a caption/annotation overlay.

        Structural heuristic (no text inspection):
          - Diagram shapes have a visible border  (a:ln with a:solidFill).
          - Caption text boxes are borderless or have transparent fill.
        """
        sp_pr = wsp.find(ns(WPS_NS, "spPr"))
        if sp_pr is None:
            return False

        ln = sp_pr.find(ns(A_NS, "ln"))
        if ln is not None and ln.find(ns(A_NS, "solidFill")) is not None:
            return True

        return False

    def _vshape_is_diagram_content(self, vshape) -> bool:
        """
        Return True if a VML shape / rect / oval is a diagram element.

        Structural heuristic:
          - stroked="t"  → visible border
          - strokecolor="..."  → visible border
        """
        stroked = (vshape.get("stroked") or "").lower()
        if stroked in ("t", "true", "1"):
            return True
        if vshape.get("strokecolor"):
            return True
        return False

    def _extract_caption_text_from_paragraph(self, p_elem) -> str:
        """
        Extract ONLY caption/annotation shape text from a drawing-only paragraph.

        Uses **structural** shape properties (border / fill transparency) to
        separate captions from diagram content – no text-regex needed.

        Caption shapes: borderless text boxes or transparent-fill overlays.
        Diagram shapes: bordered flowchart boxes, process steps, arrows.
        """
        if not self.get_shape_content:
            return ""

        candidates: List[str] = []

        # --- Helper: extract caption text from WPS shapes inside a drawing ----
        def _caption_from_drawing(drawing):
            holders = (
                list(drawing.findall(f".//{ns(WP_NS, 'inline')}"))
                + list(drawing.findall(f".//{ns(WP_NS, 'anchor')}"))
            )
            for holder in holders:
                for wsp in holder.findall(f".//{ns(WPS_NS, 'wsp')}"):
                    if self._wsp_is_diagram_content(wsp):
                        continue
                    txbx = wsp.find(ns(WPS_NS, "txbx"))
                    if txbx is None:
                        continue
                    txbx_content = txbx.find(ns(W_NS, "txbxContent"))
                    if txbx_content is not None:
                        st = self._extract_text_from_txbxContent(txbx_content)
                        if st and not self._is_marker_shape_text(st):
                            candidates.append(st)

        # mc:AlternateContent > mc:Choice drawings (modern path)
        for alt in p_elem.findall(f".//{ns(MC_NS, 'AlternateContent')}"):
            choice = alt.find(ns(MC_NS, "Choice"))
            if choice is None:
                continue
            for drawing in choice.findall(f".//{ns(W_NS, 'drawing')}"):
                _caption_from_drawing(drawing)

        # Direct w:drawing not inside mc:AlternateContent
        for drawing in p_elem.findall(f".//{ns(W_NS, 'drawing')}"):
            parent = drawing.getparent()
            inside_alt = False
            while parent is not None:
                if parent.tag == ns(MC_NS, "AlternateContent"):
                    inside_alt = True
                    break
                parent = parent.getparent()
            if inside_alt:
                continue
            _caption_from_drawing(drawing)

        # VML fallback (v:shape, v:rect, v:oval …) not inside mc:AlternateContent
        for tag in ("shape", "rect", "oval"):
            for vel in p_elem.findall(f".//{ns(V_NS, tag)}"):
                parent = vel.getparent()
                inside_alt = False
                while parent is not None:
                    if parent.tag == ns(MC_NS, "AlternateContent"):
                        inside_alt = True
                        break
                    parent = parent.getparent()
                if inside_alt:
                    continue
                if self._vshape_is_diagram_content(vel):
                    continue
                for textbox in vel.findall(f".//{ns(V_NS, 'textbox')}"):
                    txbx_content = textbox.find(ns(W_NS, "txbxContent"))
                    if txbx_content is not None:
                        st = self._extract_text_from_txbxContent(txbx_content)
                        if st and not self._is_marker_shape_text(st):
                            candidates.append(st)

        # Deduplicate while preserving order
        seen: Set[str] = set()
        kept: List[str] = []
        for s in candidates:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                kept.append(s)

        # In picture/diagram clusters, borderless text boxes may include both
        # actual captions (e.g. "図3.1-1. ...") and diagram labels (e.g.
        # "ライセンスキー").  The structural heuristic cannot distinguish them
        # because both lack a:ln borders.  Apply a content-based filter to keep
        # ONLY text that matches the caption pattern (図/表/figure/picture/table
        # followed by numbering).  This correctly suppresses diagram-internal
        # labels while preserving the real title.
        caption_kept = [s for s in kept if self._is_caption_text(s)]
        if caption_kept:
            return " ".join(caption_kept).strip()

        return ""
    
    # Set of single-character markers that should be ignored in shape text extraction.
    # These are typically used as revision markers, status indicators, or decorative elements
    # inside small text boxes overlaid on diagrams/shapes in the document.
    # Examples: Triangle with "R" inside for "Revision", etc.
    SHAPE_TEXT_MARKERS_TO_IGNORE = frozenset({
        "R",  # Revision marker (triangle with R)
    })

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

    def _extract_text_from_txbxContent(self, txbx_content) -> str:
        """
        Extract text from a w:txbxContent element (text box content inside shapes).
        Parses all paragraphs within the text box and joins them.
        """
        if txbx_content is None:
            return ""
        
        text_parts = []
        for p in txbx_content.findall(f".//{ns(W_NS, 'p')}"):
            # Extract text from runs in this paragraph
            para_parts = []

            # Field tracking: skip cached results of REF, STYLEREF, SEQ fields
            _field_stack: List[dict] = []

            for r in p.findall(f".//{ns(W_NS, 'r')}"):
                # Skip runs inside w:del (deleted text)
                parent = r.getparent()
                skip = False
                while parent is not None and parent != p:
                    if parent.tag == ns(W_NS, "del"):
                        skip = True
                        break
                    parent = parent.getparent()
                if skip:
                    continue

                # --- Field character tracking (REF / STYLEREF / SEQ) ---
                fld_char = r.find(ns(W_NS, "fldChar"))
                if fld_char is not None:
                    fld_type = fld_char.get(ns(W_NS, "fldCharType")) or ""
                    if fld_type == "begin":
                        _field_stack.append({"instr": "", "in_result": False, "skip": False})
                    elif fld_type == "separate" and _field_stack:
                        _field_stack[-1]["in_result"] = True
                    elif fld_type == "end" and _field_stack:
                        _field_stack.pop()

                # Accumulate field instruction text
                instr_el = r.find(ns(W_NS, "instrText"))
                if instr_el is not None and instr_el.text and _field_stack:
                    _field_stack[-1]["instr"] += instr_el.text
                    instr = _field_stack[-1]["instr"].strip()
                    if instr.startswith(("REF ", "STYLEREF ", "SEQ ")):
                        _field_stack[-1]["skip"] = True

                # If we are inside the result region of a field we want to skip, drop this run
                if any(f["in_result"] and f["skip"] for f in _field_stack):
                    continue

                # Extract text from t elements
                for t in r.findall(ns(W_NS, "t")):
                    if t.text:
                        para_parts.append(t.text)
                # Handle delText (in case of tracked changes kept)
                for dt in r.findall(ns(W_NS, "delText")):
                    if dt.text:
                        para_parts.append(dt.text)
                # Handle tab and br
                for tab in r.findall(ns(W_NS, "tab")):
                    para_parts.append(" ")
                for br in r.findall(ns(W_NS, "br")):
                    para_parts.append(" ")
            
            para_text = "".join(para_parts).strip()
            if para_text:
                text_parts.append(para_text)
        
        return " ".join(text_parts)

    def _extract_shapes_from_element(self, elem) -> List[str]:
        """
        Extract shape text content from an element (paragraph or run).
        
        Looks for w:drawing elements containing wp:inline or wp:anchor with:
        - wps:txbx/w:txbxContent (WordprocessingML shapes with text boxes)
        - v:textbox/w:txbxContent (VML fallback shapes)
        
        Returns list of shape content placeholder strings.
        Skips shapes that are purely images (handled by _extract_images_from_element).
        """
        if not self.get_shape_content:
            return []
        
        shape_chunks: List[str] = []

        # Process mc:AlternateContent first (preferred modern format)
        for alt_content in elem.findall(f".//{ns(MC_NS, 'AlternateContent')}"):
            choice = alt_content.find(ns(MC_NS, "Choice"))
            if choice is not None:
                # Process wp:anchor/wp:inline inside mc:Choice > w:drawing
                for drawing in choice.findall(f".//{ns(W_NS, 'drawing')}"):
                    shape_text = self._extract_shape_text_from_drawing(drawing)
                    if shape_text:
                        shape_chunks.append(
                            f"{SHAPE_CONTENT_START_MARKER} {shape_text} {SHAPE_CONTENT_END_MARKER}"
                        )

        # Process direct w:drawing elements (not inside mc:AlternateContent)
        for drawing in elem.findall(f".//{ns(W_NS, 'drawing')}"):
            # Skip if this drawing is inside an mc:AlternateContent (already processed)
            parent = drawing.getparent()
            inside_alt = False
            while parent is not None:
                if parent.tag == ns(MC_NS, "AlternateContent"):
                    inside_alt = True
                    break
                parent = parent.getparent()
            
            if inside_alt:
                continue
            
            shape_text = self._extract_shape_text_from_drawing(drawing)
            if shape_text:
                shape_chunks.append(
                    f"{SHAPE_CONTENT_START_MARKER} {shape_text} {SHAPE_CONTENT_END_MARKER}"
                )

        # Process VML shapes (v:shape with v:textbox) as fallback
        # These are usually inside mc:Fallback or in older documents
        for vshape in elem.findall(f".//{ns(V_NS, 'shape')}"):
            # Skip if inside mc:AlternateContent (we use the Choice version)
            parent = vshape.getparent()
            inside_alt = False
            while parent is not None:
                if parent.tag == ns(MC_NS, "AlternateContent"):
                    inside_alt = True
                    break
                parent = parent.getparent()
            
            if inside_alt:
                continue
            
            # Look for v:textbox > w:txbxContent
            for textbox in vshape.findall(f".//{ns(V_NS, 'textbox')}"):
                txbx_content = textbox.find(ns(W_NS, "txbxContent"))
                if txbx_content is not None:
                    shape_text = self._extract_text_from_txbxContent(txbx_content)
                    # Skip marker shapes (single-character markers like "R")
                    if shape_text and not self._is_marker_shape_text(shape_text):
                        shape_chunks.append(
                            f"{SHAPE_CONTENT_START_MARKER} {shape_text} {SHAPE_CONTENT_END_MARKER}"
                        )

        return shape_chunks

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
            list(drawing.findall(f".//{ns(WP_NS, 'inline')}"))
            + list(drawing.findall(f".//{ns(WP_NS, 'anchor')}"))
        )

        text_parts = []
        for holder in holders:
            # Look for wps:wsp (WordprocessingML shape) with wps:txbx
            for wsp in holder.findall(f".//{ns(WPS_NS, 'wsp')}"):
                txbx = wsp.find(ns(WPS_NS, "txbx"))
                if txbx is not None:
                    txbx_content = txbx.find(ns(W_NS, "txbxContent"))
                    if txbx_content is not None:
                        shape_text = self._extract_text_from_txbxContent(txbx_content)
                        # Skip marker shapes (single-character markers like "R")
                        if shape_text and not self._is_marker_shape_text(shape_text):
                            text_parts.append(shape_text)

        return " ".join(text_parts)

    def _extract_images_from_element(self, elem) -> List[str]:
        """
        Extract images from an element (paragraph or run).
        Looks for w:drawing elements containing wp:inline or wp:anchor with a:blip.
        Returns list of image placeholder strings.
        """
        image_chunks: List[str] = []

        if not self.get_image_content:
            return image_chunks

        # Find all drawing elements
        for drawing in elem.findall(f".//{ns(W_NS, 'drawing')}"):
            # Look for inline and anchor holders
            holders = (
                list(drawing.findall(f".//{ns(WP_NS, 'inline')}"))
                + list(drawing.findall(f".//{ns(WP_NS, 'anchor')}"))
            )

            for holder in holders:
                # Get description/title for caption
                doc_pr = holder.find(f".//{ns(WP_NS, 'docPr')}")
                title = (doc_pr.get("title") if doc_pr is not None else "") or ""
                descr = (doc_pr.get("descr") if doc_pr is not None else "") or ""
                caption = (descr or title).strip()

                # Find blip elements (the actual image reference)
                for blip in holder.findall(f".//{ns(A_NS, 'blip')}"):
                    embed_rid = blip.get(ns(R_NS, "embed"))
                    link_rid = blip.get(ns(R_NS, "link"))
                    rel_id = embed_rid or link_rid

                    if not rel_id:
                        continue

                    # DEDUPE by rel_id: if already saved once, reuse it
                    cached = self._image_cache_by_rid.get(rel_id)
                    if cached:
                        image_path, image_hash = cached
                        placeholder = f"{IMAGE_PATH_START_MARKER} {image_path}|{image_hash} {IMAGE_PATH_END_MARKER}"
                        image_chunks.append(placeholder)
                        continue

                    placeholder = None

                    # Resolve bytes for this rel_id
                    image_bytes, image_ext = self._resolve_image_bytes_from_rid(rel_id)

                    if image_bytes:
                        # Compute full md5 NOW (so we can dedupe by content too)
                        image_hash = self._md5(image_bytes)

                        # DEDUPE by md5: if same bytes already saved under other rel_id
                        existing_path = self._image_cache_by_hash.get(image_hash)
                        if existing_path:
                            # cache under rel_id and reuse existing file path
                            self._image_cache_by_rid[rel_id] = (existing_path, image_hash)
                            placeholder = f"{IMAGE_PATH_START_MARKER} {existing_path}|{image_hash} {IMAGE_PATH_END_MARKER}"
                            image_chunks.append(placeholder)
                            continue

                        # Not seen before: save to disk
                        saved = self._save_image_bytes(image_bytes, image_ext, rel_id=rel_id)
                        if saved:
                            image_path, saved_hash = saved  # saved_hash should equal image_hash
                            # Cache both ways
                            self._image_cache_by_rid[rel_id] = (image_path, saved_hash)
                            self._image_cache_by_hash[saved_hash] = image_path
                            placeholder = f"{IMAGE_PATH_START_MARKER} {image_path}|{saved_hash} {IMAGE_PATH_END_MARKER}"

                    if not placeholder:
                        # Keep existing behavior for missing images
                        placeholder = f"{IMAGE_PATH_START_MARKER} MISSING_IMAGE {IMAGE_PATH_END_MARKER}"

                    image_chunks.append(placeholder)

        return image_chunks

    def _extract_images_from_paragraph(self, p_elem) -> List[str]:
        """
        Extract image placeholders from a paragraph element.

        Used by flush_pending_drawing_ps to emit IMAGE_PATH markers for images
        found inside picture/diagram clusters (drawing-only paragraphs).
        Skips drawings that are inside w:txbxContent (textbox shapes).
        Skips drawings whose containing run has strikethrough formatting.
        """
        if not self.get_image_content:
            return []

        # Paragraph-level strike: check pPr/pStyle against known strike styles
        para_struck = False
        if not self.keep_strikethrough_text:
            ppr = p_elem.find(ns(W_NS, "pPr"))
            if ppr is not None:
                pstyle = ppr.find(ns(W_NS, "pStyle"))
                if pstyle is not None:
                    style_val = pstyle.get(ns(W_NS, "val"))
                    if style_val and style_val in self._strike_style_ids:
                        para_struck = True
            if para_struck:
                return []

        image_chunks: List[str] = []

        for drawing in p_elem.findall(f".//{ns(W_NS, 'drawing')}"):
            # Skip drawings inside textboxes
            parent = drawing.getparent()
            inside_txbx = False
            run_struck = False
            while parent is not None and parent != p_elem:
                if parent.tag == ns(W_NS, "txbxContent"):
                    inside_txbx = True
                    break
                # Check if the containing run has strikethrough
                if not self.keep_strikethrough_text and parent.tag == ns(W_NS, "r"):
                    rpr = parent.find(ns(W_NS, "rPr"))
                    if rpr is not None:
                        if (rpr.find(ns(W_NS, "strike")) is not None or
                                rpr.find(ns(W_NS, "dstrike")) is not None):
                            run_struck = True
                parent = parent.getparent()
            if inside_txbx or run_struck:
                continue

            holders = (
                list(drawing.findall(f".//{ns(WP_NS, 'inline')}"))
                + list(drawing.findall(f".//{ns(WP_NS, 'anchor')}"))
            )

            for holder in holders:
                for blip in holder.findall(f".//{ns(A_NS, 'blip')}"):
                    embed_rid = blip.get(ns(R_NS, "embed"))
                    link_rid = blip.get(ns(R_NS, "link"))
                    rel_id = embed_rid or link_rid
                    if not rel_id:
                        continue

                    cached = self._image_cache_by_rid.get(rel_id)
                    if cached:
                        image_path, image_hash = cached
                        placeholder = f"{IMAGE_PATH_START_MARKER} {image_path}|{image_hash} {IMAGE_PATH_END_MARKER}"
                        image_chunks.append(placeholder)
                        continue

                    placeholder = None
                    image_bytes, image_ext = self._resolve_image_bytes_from_rid(rel_id)

                    if image_bytes:
                        image_hash = self._md5(image_bytes)
                        existing_path = self._image_cache_by_hash.get(image_hash)
                        if existing_path:
                            self._image_cache_by_rid[rel_id] = (existing_path, image_hash)
                            placeholder = f"{IMAGE_PATH_START_MARKER} {existing_path}|{image_hash} {IMAGE_PATH_END_MARKER}"
                            image_chunks.append(placeholder)
                            continue

                        saved = self._save_image_bytes(image_bytes, image_ext, rel_id=rel_id)
                        if saved:
                            image_path, saved_hash = saved
                            self._image_cache_by_rid[rel_id] = (image_path, saved_hash)
                            self._image_cache_by_hash[saved_hash] = image_path
                            placeholder = f"{IMAGE_PATH_START_MARKER} {image_path}|{saved_hash} {IMAGE_PATH_END_MARKER}"

                    if not placeholder:
                        placeholder = f"{IMAGE_PATH_START_MARKER} MISSING_IMAGE {IMAGE_PATH_END_MARKER}"

                    image_chunks.append(placeholder)

        return image_chunks

    def _extract_substantial_shape_text_from_paragraph(
        self, p_elem, min_text_length: int = 100
    ) -> List[str]:
        """
        Extract text from bordered shapes with substantial content.

        In picture/diagram clusters, bordered shapes (a:ln with solidFill) that
        contain substantial multi-line text (>= min_text_length characters) are
        treated as standalone annotation rectangles whose content should be
        preserved.  Short bordered shapes (legends, labels) are skipped.
        """
        if not self.get_shape_content:
            return []

        results: List[str] = []

        def _check_wsps_in_drawing(drawing):
            holders = (
                list(drawing.findall(f".//{ns(WP_NS, 'inline')}"))
                + list(drawing.findall(f".//{ns(WP_NS, 'anchor')}"))
            )
            for holder in holders:
                for wsp in holder.findall(f".//{ns(WPS_NS, 'wsp')}"):
                    if not self._wsp_is_diagram_content(wsp):
                        continue  # borderless → skip (label/overlay)
                    txbx = wsp.find(ns(WPS_NS, "txbx"))
                    if txbx is None:
                        continue
                    txbx_content = txbx.find(ns(W_NS, "txbxContent"))
                    if txbx_content is None:
                        continue
                    text = self._extract_text_from_txbxContent(txbx_content)
                    if text and len(text.strip()) >= min_text_length:
                        results.append(text.strip())

        # mc:AlternateContent > mc:Choice drawings
        for alt in p_elem.findall(f".//{ns(MC_NS, 'AlternateContent')}"):
            choice = alt.find(ns(MC_NS, "Choice"))
            if choice is None:
                continue
            for drawing in choice.findall(f".//{ns(W_NS, 'drawing')}"):
                _check_wsps_in_drawing(drawing)

        # Direct w:drawing not inside mc:AlternateContent
        for drawing in p_elem.findall(f".//{ns(W_NS, 'drawing')}"):
            parent = drawing.getparent()
            inside_alt = False
            while parent is not None:
                if parent.tag == ns(MC_NS, "AlternateContent"):
                    inside_alt = True
                    break
                parent = parent.getparent()
            if inside_alt:
                continue
            _check_wsps_in_drawing(drawing)

        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Parse DOCX files without python-docx")
    parser.add_argument("--input", help="Path to DOCX file")
    parser.add_argument("--gray-brightness", type=float, default=180.0)
    parser.add_argument("--gray-spread", type=int, default=12)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    docx_parser = DocxParser()
    docx_parser.gray_brightness_thr = args.gray_brightness
    docx_parser.gray_spread_thr = args.gray_spread

    tree = docx_parser.extract_docx_text(args.input)
    
    # print(json.dumps(tree, ensure_ascii=False, indent=2))

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

if __name__ == "__main__":
    main()
