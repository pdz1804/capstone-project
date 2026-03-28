"""
PDF Classification Module

Classifies PDFs as born-digital, scanned, or hybrid by analyzing
page-level signals: text density, image coverage, font usage,
structure tree presence, and producer metadata.

Born-digital PDFs are routed to the custom pdf_reader parser.
Scanned/hybrid PDFs continue through Docling's OCR+VLM pipeline.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # pymupdf

logger = logging.getLogger(__name__)


class PdfType(Enum):
    BORN_DIGITAL = "born_digital"
    SCANNED = "scanned"
    HYBRID = "hybrid"


class PageType(Enum):
    BORN_DIGITAL = "born_digital"
    SCANNED = "scanned"
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


# Producer strings that indicate scanning origin
_SCANNER_PRODUCERS = [
    "scan", "fujitsu", "canon", "epson", "brother", "xerox",
    "konica", "ricoh", "sharp", "kodak", "panasonic",
    "scansnap", "paperstream", "twain",
]

# Producer strings that indicate born-digital origin
_DIGITAL_PRODUCERS = [
    "word", "latex", "pdflatex", "xelatex", "lualatex",
    "chrome", "firefox", "safari", "webkit",
    "indesign", "illustrator", "acrobat distiller",
    "libreoffice", "openoffice", "microsoft",
    "quartz", "cairo", "reportlab", "wkhtmltopdf",
    "prince", "weasyprint", "typst", "overleaf",
]

# Minimum text characters per page to consider it "has text"
_MIN_TEXT_CHARS = 50
# Maximum text characters per page below which page is "text-sparse"
_SPARSE_TEXT_CHARS = 20
# Image coverage threshold above which page looks like a scan
_HIGH_IMAGE_COVERAGE = 0.80
# Image coverage threshold below which page looks born-digital
_LOW_IMAGE_COVERAGE = 0.50
# Percentage threshold for aggregating page classifications
_MAJORITY_THRESHOLD = 0.70


class PdfClassifier:
    """Classify a PDF as born-digital, scanned, or hybrid."""

    def classify(self, file_path: str | Path) -> PdfClassification:
        """Classify a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            PdfClassification with type, confidence, and diagnostic signals.
        """
        file_path = Path(file_path)
        doc = fitz.open(str(file_path))

        try:
            return self._classify_document(doc)
        finally:
            doc.close()

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

        # --- Sample pages ---
        sample_indices = self._pick_sample_pages(page_count)
        page_results: List[Dict[str, Any]] = []
        page_types: List[PageType] = []

        for idx in sample_indices:
            page = doc[idx]
            result = self._analyze_page(page)
            page_results.append(result)
            page_types.append(result["page_type"])

        # --- Aggregate ---
        born_count = sum(1 for t in page_types if t == PageType.BORN_DIGITAL)
        scanned_count = sum(1 for t in page_types if t == PageType.SCANNED)
        total_sampled = len(page_types)

        born_ratio = born_count / total_sampled
        scanned_ratio = scanned_count / total_sampled

        # Start with page-level majority vote
        if born_ratio >= _MAJORITY_THRESHOLD:
            pdf_type = PdfType.BORN_DIGITAL
            confidence = born_ratio
        elif scanned_ratio >= _MAJORITY_THRESHOLD:
            pdf_type = PdfType.SCANNED
            confidence = scanned_ratio
        else:
            pdf_type = PdfType.HYBRID
            confidence = max(born_ratio, scanned_ratio)

        # --- Apply global signal adjustments ---

        # Structure tree is a strong born-digital indicator
        if has_structure_tree and pdf_type != PdfType.BORN_DIGITAL:
            if born_ratio >= 0.4:
                pdf_type = PdfType.BORN_DIGITAL
                confidence = max(confidence, 0.75)

        # ToC is a moderate born-digital indicator
        if has_toc and pdf_type == PdfType.HYBRID:
            pdf_type = PdfType.BORN_DIGITAL
            confidence = max(confidence, 0.65)

        # Producer metadata can tip uncertain cases
        if producer_signal == "digital" and pdf_type == PdfType.HYBRID:
            pdf_type = PdfType.BORN_DIGITAL
            confidence = max(confidence, 0.60)
        elif producer_signal == "scanner" and pdf_type == PdfType.HYBRID:
            pdf_type = PdfType.SCANNED
            confidence = max(confidence, 0.60)

        # Build full page classification list (sampled pages only have results)
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

    def _pick_sample_pages(self, page_count: int) -> List[int]:
        """Pick representative pages to sample (max 5)."""
        if page_count <= 5:
            return list(range(page_count))

        indices = set()
        # First 3 pages
        for i in range(min(3, page_count)):
            indices.add(i)
        # Middle page
        indices.add(page_count // 2)
        # Last page
        indices.add(page_count - 1)

        return sorted(indices)

    def _analyze_page(self, page: fitz.Page) -> Dict[str, Any]:
        """Analyze a single page and classify it."""
        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return {"page_type": PageType.UNCERTAIN, "text_chars": 0, "image_coverage": 0}

        # --- Text analysis ---
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        total_chars = 0
        font_names = set()

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # type 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    total_chars += len(text)
                    if span.get("font"):
                        font_names.add(span["font"])

        # --- Image analysis ---
        images = page.get_images(full=True)
        image_area_total = 0.0

        for img in images:
            xref = img[0]
            try:
                # Get image bbox on the page
                img_rects = page.get_image_rects(xref)
                for rect in img_rects:
                    image_area_total += rect.width * rect.height
            except Exception:
                # Fallback: use image dimensions from xref
                try:
                    w, h = img[2], img[3]  # width, height from get_images
                    image_area_total += w * h * 0.5  # rough estimate
                except Exception:
                    pass

        image_coverage = min(image_area_total / page_area, 1.0) if page_area > 0 else 0

        # --- Classify page ---
        if total_chars >= _MIN_TEXT_CHARS and image_coverage < _LOW_IMAGE_COVERAGE:
            page_type = PageType.BORN_DIGITAL
        elif total_chars < _SPARSE_TEXT_CHARS and image_coverage > _HIGH_IMAGE_COVERAGE:
            page_type = PageType.SCANNED
        elif total_chars >= _MIN_TEXT_CHARS:
            # Has text but also high image coverage — likely born-digital with figures
            page_type = PageType.BORN_DIGITAL
        elif image_coverage > _HIGH_IMAGE_COVERAGE:
            # Very high image coverage, sparse text — likely scanned with OCR layer
            page_type = PageType.SCANNED
        else:
            page_type = PageType.UNCERTAIN

        return {
            "page_type": page_type,
            "text_chars": total_chars,
            "image_coverage": round(image_coverage, 3),
            "font_count": len(font_names),
            "fonts": list(font_names)[:10],
            "image_count": len(images),
        }

    def _get_pdf_version(self, doc: fitz.Document) -> str:
        """Extract PDF version from the header (e.g. '1.7')."""
        try:
            # pymupdf exposes version info
            # Try reading first bytes for %PDF-x.y
            first_bytes = doc.tobytes()[:20] if doc.page_count > 0 else b""
            if first_bytes.startswith(b"%PDF-"):
                version_str = first_bytes[5:8].decode("ascii", errors="ignore")
                return version_str.strip()
        except Exception:
            pass
        return "unknown"

    def _has_structure_tree(self, doc: fitz.Document) -> bool:
        """Check if the PDF has a structure tree (Tagged PDF)."""
        try:
            # pymupdf: check catalog for MarkInfo or StructTreeRoot
            cat = doc.pdf_catalog()
            if cat > 0:
                xref_str = doc.xref_object(cat)
                return "/StructTreeRoot" in xref_str or "/MarkInfo" in xref_str
        except Exception:
            pass
        return False

    def _check_producer(self, doc: fitz.Document) -> str:
        """Check producer/creator metadata for scan vs digital signals.

        Returns: 'digital', 'scanner', or 'unknown'.
        """
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
