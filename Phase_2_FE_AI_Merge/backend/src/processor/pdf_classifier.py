"""
PDF Classification Module

Classifies PDFs as born-digital, scanned (with/without OCR), or hybrid
by analysing **content-stream operators** — the actual drawing instructions
inside each page — rather than pixel-level heuristics.

Key signals (ranked by reliability):

1. **Content-stream operators**
   - ``BT``/``ET`` + ``Tj``/``TJ`` with render-mode 0 → born-digital text
   - Zero text operators, only ``q cm Do Q`` → scanned (no OCR)
   - ``Tr 3`` (invisible text) → scanned with OCR overlay

2. **Font analysis**
   - Real font names with ``/FontFile`` → born-digital
   - ``/GlyphLessFont`` or similar synthetic names → OCR font
   - Zero fonts on page → no text layer at all

3. **Global metadata** (tie-breakers)
   - ``/StructTreeRoot`` → strong born-digital signal
   - ``/Producer`` / ``/Creator`` keywords
   - Table-of-contents bookmarks
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # pymupdf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public enums & dataclass
# ---------------------------------------------------------------------------

class PdfType(Enum):
    BORN_DIGITAL = "born_digital"
    SCANNED = "scanned"
    HYBRID = "hybrid"


class PageType(Enum):
    BORN_DIGITAL = "born_digital"
    SCANNED_NO_OCR = "scanned_no_ocr"
    SCANNED_WITH_OCR = "scanned_with_ocr"
    UNCERTAIN = "uncertain"


@dataclass
class PdfClassification:
    pdf_type: PdfType
    confidence: float
    page_classifications: List[str]
    signals: Dict[str, Any]
    pdf_version: str
    has_structure_tree: bool
    page_count: int


# ---------------------------------------------------------------------------
# Producer / creator keyword lists (tier-3 tie-breaker)
# ---------------------------------------------------------------------------

_SCANNER_PRODUCERS = [
    "scan", "fujitsu", "canon", "epson", "brother", "xerox",
    "konica", "ricoh", "sharp", "kodak", "panasonic",
    "scansnap", "paperstream", "twain",
]

_DIGITAL_PRODUCERS = [
    "word", "latex", "pdflatex", "xelatex", "lualatex",
    "chrome", "firefox", "safari", "webkit",
    "indesign", "illustrator", "acrobat distiller",
    "libreoffice", "openoffice", "microsoft",
    "quartz", "cairo", "reportlab", "wkhtmltopdf",
    "prince", "weasyprint", "typst", "overleaf",
    "canva", "ghostscript",
]

# Font base-names that indicate an OCR text layer
_OCR_FONT_NAMES = [
    "glyphlessFont", "invisible", "hiddenhocrtext",
]

# Majority-vote threshold
_MAJORITY_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class PdfClassifier:
    """Classify a PDF as born-digital, scanned, or hybrid using
    content-stream operator analysis."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, file_path: str | Path) -> PdfClassification:
        file_path = Path(file_path)
        doc = fitz.open(str(file_path))
        try:
            return self._classify_document(doc)
        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Document-level classification
    # ------------------------------------------------------------------

    def _classify_document(self, doc: fitz.Document) -> PdfClassification:
        page_count = len(doc)
        if page_count == 0:
            return PdfClassification(
                pdf_type=PdfType.SCANNED,
                confidence=0.5,
                page_classifications=[],
                signals={"reason": "empty_document"},
                pdf_version=self._get_pdf_version(doc),
                has_structure_tree=False,
                page_count=0,
            )

        # --- Global signals ---
        pdf_version = self._get_pdf_version(doc)
        has_structure_tree = self._has_structure_tree(doc)
        toc = doc.get_toc()
        has_toc = len(toc) > 0
        producer_signal = self._check_producer(doc)

        # --- Per-page content-stream analysis ---
        sample_indices = self._pick_sample_pages(page_count)
        page_results: List[Dict[str, Any]] = []
        page_types: List[PageType] = []

        for idx in sample_indices:
            result = self._analyze_page(doc, idx)
            page_results.append(result)
            page_types.append(result["page_type"])

        # --- Aggregate page votes → initial type + confidence ---
        born_ratio, scanned_ratio = self._compute_ratios(page_types)
        pdf_type, confidence = self._majority_vote(born_ratio, scanned_ratio)

        # --- Apply global-signal adjustments ---
        pdf_type, confidence = self._apply_global_signals(
            pdf_type, confidence, born_ratio,
            has_structure_tree, has_toc, producer_signal,
        )

        # Full page classification list
        full_page_classifications = ["unknown"] * page_count
        for i, idx in enumerate(sample_indices):
            full_page_classifications[idx] = page_types[i].value

        signals = {
            "sampled_pages": sample_indices,
            "born_ratio": round(born_ratio, 3),
            "scanned_ratio": round(scanned_ratio, 3),
            "has_toc": has_toc,
            "toc_entries": len(toc),
            "producer_signal": producer_signal,
            "producer": doc.metadata.get("producer", ""),
            "creator": doc.metadata.get("creator", ""),
            "page_details": page_results,
        }

        return PdfClassification(
            pdf_type=pdf_type,
            confidence=round(confidence, 3),
            page_classifications=full_page_classifications,
            signals=signals,
            pdf_version=pdf_version,
            has_structure_tree=has_structure_tree,
            page_count=page_count,
        )

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_ratios(page_types: List[PageType]) -> tuple[float, float]:
        total = len(page_types)
        born = sum(1 for t in page_types if t == PageType.BORN_DIGITAL)
        scanned = sum(
            1 for t in page_types
            if t in (PageType.SCANNED_NO_OCR, PageType.SCANNED_WITH_OCR)
        )
        return born / total, scanned / total

    @staticmethod
    def _majority_vote(
        born_ratio: float, scanned_ratio: float,
    ) -> tuple[PdfType, float]:
        if born_ratio >= _MAJORITY_THRESHOLD:
            return PdfType.BORN_DIGITAL, born_ratio
        if scanned_ratio >= _MAJORITY_THRESHOLD:
            return PdfType.SCANNED, scanned_ratio
        return PdfType.HYBRID, max(born_ratio, scanned_ratio)

    @staticmethod
    def _apply_global_signals(
        pdf_type: PdfType,
        confidence: float,
        born_ratio: float,
        has_structure_tree: bool,
        has_toc: bool,
        producer_signal: str,
    ) -> tuple[PdfType, float]:
        if has_structure_tree and pdf_type != PdfType.BORN_DIGITAL and born_ratio >= 0.4:
            return PdfType.BORN_DIGITAL, max(confidence, 0.75)

        if pdf_type != PdfType.HYBRID:
            return pdf_type, confidence

        # Hybrid tie-breakers
        if has_toc:
            return PdfType.BORN_DIGITAL, max(confidence, 0.65)
        if producer_signal == "digital":
            return PdfType.BORN_DIGITAL, max(confidence, 0.60)
        if producer_signal == "scanner":
            return PdfType.SCANNED, max(confidence, 0.60)

        return pdf_type, confidence

    # ------------------------------------------------------------------
    # Page-level content-stream analysis  (TIER 1 — definitive)
    # ------------------------------------------------------------------

    def _analyze_page(self, doc: fitz.Document, page_idx: int) -> Dict[str, Any]:
        """Classify a single page by inspecting its content-stream operators."""
        page = doc[page_idx]

        # --- Parse content stream ---
        text_ops = 0      # Tj + TJ count
        bt_count = 0      # BT blocks
        do_count = 0      # XObject paint (images / forms)
        has_invisible_text = False  # Tr 3

        for xref in page.get_contents():
            stream = doc.xref_stream(xref)
            if not stream:
                continue
            raw = stream.decode("latin-1", errors="ignore")

            text_ops += len(re.findall(r"\bTj\b", raw))
            text_ops += len(re.findall(r"\bTJ\b", raw))
            bt_count += len(re.findall(r"\bBT\b", raw))
            do_count += len(re.findall(r"\bDo\b", raw))

            # Invisible-text render mode (mode 3)
            if re.search(r"3\s+Tr\b", raw):
                has_invisible_text = True

        # --- Font analysis (TIER 2) ---
        fonts = page.get_fonts()
        font_names = [f[3] for f in fonts]  # basefont name
        has_ocr_font = any(
            any(kw.lower() in name.lower() for kw in _OCR_FONT_NAMES)
            for name in font_names
        )

        # --- Classify page ---
        if text_ops == 0 and bt_count == 0 and len(fonts) == 0:
            page_type = PageType.SCANNED_NO_OCR
        elif has_invisible_text or has_ocr_font:
            page_type = PageType.SCANNED_WITH_OCR
        elif text_ops > 0:
            page_type = PageType.BORN_DIGITAL
        elif bt_count > 0 and len(fonts) > 0:
            # BT/ET blocks exist but no Tj/TJ — unusual but treat as born-digital
            page_type = PageType.BORN_DIGITAL
        else:
            page_type = PageType.UNCERTAIN

        return {
            "page_type": page_type,
            "text_ops": text_ops,
            "bt_blocks": bt_count,
            "do_ops": do_count,
            "has_invisible_text": has_invisible_text,
            "font_count": len(fonts),
            "font_names": font_names[:10],
            "has_ocr_font": has_ocr_font,
        }

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _pick_sample_pages(self, page_count: int) -> List[int]:
        if page_count <= 5:
            return list(range(page_count))
        indices = set()
        for i in range(min(3, page_count)):
            indices.add(i)
        indices.add(page_count // 2)
        indices.add(page_count - 1)
        return sorted(indices)

    # ------------------------------------------------------------------
    # Global metadata helpers (TIER 3 — tie-breakers)
    # ------------------------------------------------------------------

    def _get_pdf_version(self, doc: fitz.Document) -> str:
        try:
            first_bytes = doc.tobytes()[:20] if doc.page_count > 0 else b""
            if first_bytes.startswith(b"%PDF-"):
                return first_bytes[5:8].decode("ascii", errors="ignore").strip()
        except Exception:
            pass
        return "unknown"

    def _has_structure_tree(self, doc: fitz.Document) -> bool:
        try:
            cat = doc.pdf_catalog()
            if cat > 0:
                xref_str = doc.xref_object(cat)
                return "/StructTreeRoot" in xref_str or "/MarkInfo" in xref_str
        except Exception:
            pass
        return False

    def _check_producer(self, doc: fitz.Document) -> str:
        producer = (doc.metadata.get("producer") or "").lower()
        creator = (doc.metadata.get("creator") or "").lower()
        combined = f"{producer} {creator}"

        for keyword in _SCANNER_PRODUCERS:
            if keyword in combined:
                return "scanner"
        for keyword in _DIGITAL_PRODUCERS:
            if keyword in combined:
                return "digital"
        return "unknown"
