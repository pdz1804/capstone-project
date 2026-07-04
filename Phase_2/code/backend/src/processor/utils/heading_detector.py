"""
heading_detector.py

Ready-to-paste Python module for robust heading detection (L1-L4+).
- Provides compiled regex lists for Level 1, 2, 3, and 4+.
- Normalizes common unicode variants (full-width digits, spaces, dashes).
- Strips leading bullet symbols before pattern matching.
- Exposes detect_heading_level(line) -> (level:int or None, pattern_name:str, match:re.Match or None).
- Configurable flags at top of file.
"""

import re
from typing import Optional, Tuple

# -------------------------
# Configuration flags
# -------------------------
MAX_HEADING_DEPTH = 3            # treat 4+ as content by default; set >3 to promote deeper headings
ALLOW_FULLWIDTH = True           # accept full-width digits and punctuation
ALLOW_ROMAN_NUMERALS = True      # accept I, II, III as top-level headings

# Bullet/symbol prefixes that should be stripped before pattern matching
SYMBOL_PREFIXES = ''.join([
    '\u25B2', '\u25BC', '\u25B3', '\u25BD', '\u25C6', '\u25CB', '\u25CF', '\u2605',
    '◆', '▽', '▼', '▲', '※', '＊', '•', '・', '◦',
    '▪', '▶', '►', '▷', '★', '☆', '➢', '➤', '➥', '→', '⇒', '○', '●', '■', '□'
])

# Pattern to strip leading bullets/symbols (used in normalization)
LEADING_BULLET_PATTERN = re.compile(rf'^[\s{re.escape(SYMBOL_PREFIXES)}\-\*]+')

# Precompiled normalization maps
_FULLWIDTH_TO_ASCII = str.maketrans(
    '０１２３４５６７８９．，：；（）［］｛｝＋－＝／＼　',
    '0123456789.,:;()[]{}+-=\\/ '
)

# -------------------------
# Normalization helpers
# -------------------------
def normalize_line(s: str, strip_bullets: bool = True) -> str:
    """
    Trim and normalize common full-width characters, dash variants, and optionally strip leading bullets.
    
    Args:
        s: Input string to normalize
        strip_bullets: If True, strips leading bullet symbols (・, •, ▶, etc.)
    
    Returns:
        Normalized string
    """
    if not s:
        return ""
    
    # Strip leading bullets/symbols first (before other normalization)
    if strip_bullets:
        s = LEADING_BULLET_PATTERN.sub('', s)
    
    if ALLOW_FULLWIDTH:
        s = s.translate(_FULLWIDTH_TO_ASCII)
    
    # ensure a space after a numeric dot when followed immediately by CJK (e.g., "1.概要" -> "1. 概要")
    s = re.sub(r'([0-9])\.(?=[\u3040-\u30FF\u4E00-\u9FFF])', r'\1. ', s)
    
    s = re.sub(r'[–—−―]', '-', s)
    # normalize multiple spaces and full-width space to single ASCII space
    s = re.sub(r'[\u3000\s]+', ' ', s).strip()
    return s

# -------------------------
# Representative regex patterns
# -------------------------
# CJK range and basic tokens
CJK = r'\u3040-\u30FF\u4E00-\u9FFF'
ASCII_UPPER = r'A-Z'
ASCII_WORD = r'[A-Za-z]+'

# Level 4+ (most specific) - detect 4 or more numeric groups using DOT separators only
# Note: This excludes chapter-section formats like 4-1.2.3 which are L3
HEADING_LEVEL_4_PLUS_PATTERNS = [
    # Mirrors L3 cases but for 4+ numeric groups (at least 4 groups: first + {3,})
    ("L4_numeric_cjk", re.compile(rf'^[ \t]*([0-9]+)(?:[．\.]([0-9]+)){{3,}}(?:[．\.])?\s*[{CJK}A-Za-z]')),
    ("L4_numeric_english", re.compile(rf'^[ \t]*([0-9]+)(?:[．\.]([0-9]+)){{3,}}(?:[．\.]|\))?\s+[A-Z]')),
    ("L4_bilingual_slash", re.compile(rf'^[ \t]*([0-9]+)(?:[．\.]([0-9]+)){{3,}}(?:[．\.])?\s*(?:/|／)\s*[A-Z{CJK}]')),
    ("L4_fullwidth", re.compile(rf'^[ \t]*([０-９]+)(?:[．\.]([０-９]+)){{3,}}(?:[．\.])?\s*')),
    # Chapter-section variants with 3+ dot-separated subgroups after the hyphen (e.g., 4-1.2.3.4)
    ("L4_chapter_section", re.compile(rf'^[ \t]*([0-9]+)-([0-9]+)(?:[．\.]([0-9]+)){{3,}}(?:[．\.])?\s*')),
    ("L4_chapter_section_fullwidth", re.compile(rf'^[ \t]*([０-９]+)-([０-９]+)(?:[．\.]([０-９]+)){{3,}}(?:[．\.])?\s*')),
    # Generic catch-alls for 4+ dot-separated numeric groups (keeps original broader patterns)
    ("L4plus_numeric_dot", re.compile(rf'^[ \t]*([0-9]+)(?:[．\.]([0-9]+)){{3,}}(?:[．\.])?\s*')),
    ("L4plus_fullwidth_numeric_dot", re.compile(rf'^[ \t]*([０-９]+)(?:[．\.]([０-９]+)){{3,}}(?:[．\.])?\s*')),
]

# Level 3 patterns
# Note: For X.Y.Z format only - chapter-section formats like 4-1.2.3 handled separately
HEADING_LEVEL_3_PATTERNS = [
    # X.Y.Z format with CJK (e.g., "1.1.1詳細" or "1.1.1. 詳細")
    ("L3_numeric_cjk", re.compile(rf'^[ \t]*([0-9]+)[．\.]([0-9]+)[．\.]([0-9]+)(?:[．\.])?\s*[{CJK}A-Za-z]')),
    # X.Y.Z format with English (e.g., "1.1.1 Title" or "1.1.1. Title" or "1.1.1) Title")
    ("L3_numeric_english", re.compile(rf'^[ \t]*([0-9]+)[．\.]([0-9]+)[．\.]([0-9]+)(?:[．\.]|\))?\s+[A-Z]')),
    # X.Y.Z with slash bilingual (e.g., "1.1.1 / English title" or "1.1.1. / English")
    ("L3_bilingual_slash", re.compile(rf'^[ \t]*([0-9]+)[．\.]([0-9]+)[．\.]([0-9]+)(?:[．\.])?\s*(?:/|／)\s*[A-Z{CJK}]')),
    # Full-width: "１．１．１" optionally with trailing dot
    ("L3_fullwidth", re.compile(rf'^[ \t]*([０-９]+)[．\.]([０-９]+)[．\.]([０-９]+)(?:[．\.])?\s*')),
    # Chapter-section format: 4-1.2.3 (chapter-section.sub.subsub) allow fullwidth dots and optional trailing dot
    ("L3_chapter_section", re.compile(rf'^[ \t]*([0-9]+)-([0-9]+)[．\.]([0-9]+)[．\.]([0-9]+)(?:[．\.])?')),
]

# Level 2 patterns
# Note: For X.Y format only - hyphen-separated X-Y patterns are handled as L1 (chapter-section)
HEADING_LEVEL_2_PATTERNS = [
    # X.Y format with CJK (e.g., "1.1概要" or "1.1 概要" or "1.1. 概要")
    ("L2_numeric_cjk", re.compile(rf'^[ \t]*([0-9]+)\.([0-9]+)(?:[．\.])?\s*[{CJK}]')),
    # X.Y format with English title (e.g., "1.1 Title" or "0.1. Title")
    ("L2_numeric_english", re.compile(rf'^[ \t]*([0-9]+)\.([0-9]+)\.?\s+[A-Z]')),
    # X.Y with slash bilingual (e.g., "1.1 / English title")
    ("L2_slash_bilingual", re.compile(rf'^[ \t]*([0-9]+)\.([0-9]+)\s*(?:/|／)\s*[A-Z{CJK}]')),
    # Letter-number format (e.g., "A.1 Title" or "A-1 Title")
    ("L2_letter_number", re.compile(rf'^[ \t]*[A-Z][.\-]([0-9]+)\s+[A-Z{CJK}]')),
    # Parenthesized (e.g., "(1.2) Purpose")
    ("L2_parenthesized", re.compile(rf'^[ \t]*\(?([0-9]+)\.([0-9]+)\)?\s+[A-Z{CJK}]')),
    # Full-width: "１．１ "
    ("L2_fullwidth", re.compile(rf'^[ \t]*([０-９]+)[．\.]([０-９]+)\s*')),
    # Chapter-section format with dot: 4-1.2 Title (chapter-section.sub)
    ("L2_chapter_section", re.compile(rf'^[ \t]*([0-9]+)-([0-9]+)\.([0-9]+)\s*[{CJK}A-Za-z]')),
]

# Level 1 patterns (least numeric groups but top-level)
L1_PATTERNS = [
    # Number + dot + space + CJK or English (e.g., "6. データ接続" or "6. Title")
    ("L1_number_dot_space_cjk", re.compile(rf'^[ \t]*([0-9]+)\.\s+[{CJK}]')),
    ("L1_number_dot_space_title", re.compile(rf'^[ \t]*([0-9]+)\.\s+[A-Z][a-z]')),
    # Single digit followed by space then title
    ("L1_single_digit_title", re.compile(rf'^[ \t]*([0-9]+)\s+[A-Z{CJK}]')),
    # Single digit immediately followed by CJK (e.g., "1概要")
    ("L1_single_digit_cjk_immediate", re.compile(rf'^[ \t]*([0-9]+)\s*[{CJK}]')),
    # Chapter-section base format: 4-1 Title or 4-0 Title  
    ("L1_chapter_section_base", re.compile(rf'^[ \t]*([0-9]+)-([0-9]+)\s+[A-Z{CJK}]')),
    # Chapter/Section keywords
    ("L1_chapter_keyword", re.compile(r'^[ \t]*(?:Chapter|CHAPTER|Section|SECTION)\s+([0-9]+|[IVXLCDM]+)\b', re.IGNORECASE)),
    # Japanese chapter format: 第1章
    ("L1_japanese_chapter", re.compile(rf'^[ \t]*第\s*([0-9０-９一二三四五六七八九十百千]+)\s*章')),
    # Roman numerals: I. Introduction
    ("L1_roman", re.compile(rf'^[ \t]*([IVXLCDM]+|[ivxlcdm]+)\.?\s+[A-Z{CJK}]')),
    # Lettered: A. Scope
    ("L1_lettered", re.compile(rf'^[ \t]*[A-Z]\.?\s+[A-Z][a-zA-Z{CJK}]')),
    # Symbol prefixed with number (after bullet stripped): "R 19 Remote Audio..." 
    ("L1_symbol_prefixed", re.compile(rf'^[ \t]*[{re.escape(SYMBOL_PREFIXES)}]?\s*[A-Za-z]?\s*[0-9０-９]+\s*[\.\-]?\s+.*[{CJK}]')),
    # Multi-word English title: "2. Testing Throughout the Software Development Lifecycle"
    ("L1_multiword_english", re.compile(rf'^[ \t]*([0-9]+)\.\s+[A-Z][a-z]+(?:\s+[A-Za-z]+)+\s*$')),
    # Short capitalized title with number: "0. Introduction"
    ("L1_short_title", re.compile(rf'^[ \t]*([0-9]+)\.\s+[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*\s*$')),
    # Number + dot + space + CJK + English bilingual: "5. 対象地域　TARGET REGIONS"
    ("L1_bilingual_cjk_en", re.compile(rf'^[ \t]*([0-9]+)\.\s+[{CJK}].*[A-Z]{{2,}}')),
    # Fullwidth number: "１．概要"
    ("L1_fullwidth_number", re.compile(rf'^[ \t]*([０-９]+)[．\.]\s*[{CJK}]')),
    # Fullwidth + ASCII then CJK: "６． CAN通信仕様"
    ("L1_fullwidth_ascii_cjk", re.compile(rf'^[ \t]*([０-９]+)[．\.]\s*[A-Za-z]+\s*[{CJK}]')),
    # Multiple space-separated numbers then title: "1 2 3 Title"
    ("L1_multi_number_title", re.compile(rf'^[ \t]*[0-9]+(?:\s+[0-9]+)+\s+[A-Z0-9{CJK}]')),
]

# Ordered precedence: check deeper patterns first
PATTERN_LEVELS = [
    (4, HEADING_LEVEL_4_PLUS_PATTERNS),
    (3, HEADING_LEVEL_3_PATTERNS),
    (2, HEADING_LEVEL_2_PATTERNS),
    (1, L1_PATTERNS),
]

# -------------------------
# Detection function
# -------------------------
def detect_heading_level(line: str, strip_bullets: bool = True) -> Tuple[Optional[int], Optional[str], Optional[re.Match]]:
    """
    Detect heading level for a single line.
    
    Args:
        line: The text line to analyze
        strip_bullets: Whether to strip leading bullet symbols before matching
    
    Returns:
        Tuple of (level, pattern_name, match) where:
        - level is 0..MAX_HEADING_DEPTH or None (0 = base pattern match)
        - pattern_name is the name of the matched pattern
        - match is the re.Match object or None
        
    If a 4+ pattern matches and MAX_HEADING_DEPTH < 4, returns (None, pattern_name, match)
    to indicate it should be treated as content, not a heading.
    """
    if not line or not line.strip():
        return None, None, None

    normalized = normalize_line(line, strip_bullets=strip_bullets)
    
    if not normalized:
        return None, None, None
    
    # Precedence: most specific (4+) first
    for level, patterns in PATTERN_LEVELS:
        for name, pat in patterns:
            m = pat.match(normalized)
            if m:
                # If this is deeper than allowed, treat as content
                if level > MAX_HEADING_DEPTH:
                    return None, name, m
                return level, name, m
    
    # Unnumbered headings heuristics (all-caps, title-case short lines)
    # if re.match(r'^[ \t]*[A-Z][A-Z0-9\s\-]{3,}$', normalized) and len(normalized.split()) <= 6:
    #     return 1, "L1_all_caps_heuristic", None
    # if re.match(r'^[ \t]*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}$', normalized) and len(normalized.split()) <= 6:
    #     return 1, "L1_titlecase_heuristic", None

    return None, None, None

# -------------------------
# Simple test harness
# -------------------------
if __name__ == "__main__":
    SAMPLE_LINES = [
        "1 Title",
        "1.1 Overview",
        "1.1.1 詳細",
        "1.1.1.1 Nested detail",
        "第1章 システム概要",
        "Chapter 2: Design",
        "I. Introduction",
        "A. Scope",
        "▽R 19 Remote Audio Volume Controlの対応による音量について",
        "１．概要",
        "1-1 機能",
        "(1.2) Purpose",
        "1.2 / Purpose",
        "APPENDIX A",
        "Short Title",
        "This is a normal sentence with 1.1 inline decimal.",
        "・6. データ接続　Data Connectivity",
        "・5. 対象地域　TARGET REGIONS",
        "6. データ接続　Data Connectivity",
        "5. 対象地域　TARGET REGIONS",
        "4-1 機能概要",
        "4-1.2 Screen Switch",
        "4-1.2.3 Sub Feature",
        "Apple",
        "13.1. HUはホーム画面でストリーミングオーディオコントロールをサポートできる必要がある。HU must be able to provide support Streaming Audio ▲b controls on the home screen.",
        "12.1.19. 外部周辺機器　External Peripherals"
    ]

    print("=" * 80)
    print("Heading Detection Test Results")
    print("=" * 80)
    for ln in SAMPLE_LINES:
        lvl, pname, match = detect_heading_level(ln)
        normalized = normalize_line(ln)
        print(f"Input: {ln!r}")
        print(f"  Normalized: {normalized!r}")
        print(f"  Level: {lvl}, Pattern: {pname}, Match: {bool(match)}")
        print()
