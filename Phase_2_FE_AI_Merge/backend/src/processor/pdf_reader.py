"""Custom PDF reader (lightweight PyMuPDF text-block path).

Pipeline:
1. Build heading hierarchy (bookmarks, then font analysis fallback)
2. Extract text blocks via PyMuPDF
3. Sequence text blocks into Docling-like heading tree JSON
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import re

try:
    from .item_sequencer import ItemSequencer, ItemSequencerConfig, SectionNode
except ImportError:
    from item_sequencer import ItemSequencer, ItemSequencerConfig, SectionNode

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLayoutRegion:
    """Minimal layout region used by ItemSequencer."""

    region_id: str
    page_no: int
    region_type: str = "text"


@dataclass
class ExtractedRegion:
    """Minimal extracted payload used by ItemSequencer."""

    region: ExtractedLayoutRegion
    text: str = ""
    markdown_table: Optional[str] = None
    latex: Optional[str] = None
    image_rel_path: Optional[str] = None
    image_md5: Optional[str] = None
    ocr_used: bool = False
    provenance: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            self.provenance = {}


@dataclass
class CustomPdfConfig:
    """Configuration for custom modular PDF extraction."""

    enable_ocr: bool = True
    ocr_mode: str = "off"  # kept for CLI compatibility
    ocr_engine: str = "rapidocr"  # kept for CLI compatibility
    extract_images: bool = False  # kept for CLI compatibility
    extract_tables: bool = False  # kept for CLI compatibility
    preserve_caption_text: bool = True  # kept for CLI compatibility
    enable_paddle_layout: bool = False  # kept for CLI compatibility
    debug_region_types: bool = False
    # Content extraction source: "pymupdf" | "docling" | "hybrid"
    #   pymupdf: legacy text-blocks only (fast, no tables/formulas).
    #   docling: Docling for text+tables+formulas+pictures.
    #   hybrid : Docling first, fallback to pymupdf blocks on Docling failure.
    content_source: str = "pymupdf"
    runtime_yaml: Optional[Dict[str, Any]] = None


class CustomPdfReader:
    """Read PDF into hierarchy-preserving JSON sections."""

    def __init__(self, config: Optional[CustomPdfConfig] = None) -> None:
        self.config = config or CustomPdfConfig()
        self.item_sequencer = ItemSequencer(ItemSequencerConfig())

    def read(
        self,
        file_path: str,
        output_dir: Optional[str] = None,
        skip_ocr: bool = False,
    ) -> List[Dict[str, Any]]:
        """Parse PDF and return section tree.

        Output schema matches previous reader:
        [{heading_text, heading_level, content, children}, ...]
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        section_tree, total_pages = self._extract_hierarchy(file_path)
        extracted = self._extract_content(file_path, output_dir)
        tree = self.item_sequencer.sequence(extracted, section_tree)

        logger.info(
            "CustomPdfReader: %s -> sections=%d pages=%d text_blocks=%d",
            p.name,
            self._count_sections(tree),
            total_pages,
            len(extracted),
        )
        if skip_ocr:
            logger.debug("skip_ocr was requested but OCR is not used in lightweight mode")
        return tree

    def _extract_content(
        self, pdf_path: str, output_dir: Optional[str],
    ) -> List[ExtractedRegion]:
        """Route to the configured content source."""
        source = (self.config.content_source or "pymupdf").lower()

        if source == "docling":
            from .docling_remote import should_use_sagemaker_docling
            if should_use_sagemaker_docling(self.config.runtime_yaml):
                from .docling_regions import extract_regions_from_sagemaker_docling
                return extract_regions_from_sagemaker_docling(
                    pdf_path,
                    runtime_yaml=self.config.runtime_yaml or {},
                    output_dir=output_dir,
                )

            from .docling_regions import extract_regions_from_docling
            return extract_regions_from_docling(
                pdf_path,
                enable_ocr=self.config.enable_ocr,
                extract_images=self.config.extract_images,
                output_dir=output_dir,
            )

        if source == "hybrid":
            try:
                from .docling_remote import should_use_sagemaker_docling
                if should_use_sagemaker_docling(self.config.runtime_yaml):
                    from .docling_regions import extract_regions_from_sagemaker_docling
                    return extract_regions_from_sagemaker_docling(
                        pdf_path,
                        runtime_yaml=self.config.runtime_yaml or {},
                        output_dir=output_dir,
                    )

                from .docling_regions import extract_regions_from_docling
                return extract_regions_from_docling(
                    pdf_path,
                    enable_ocr=self.config.enable_ocr,
                    extract_images=self.config.extract_images,
                    output_dir=output_dir,
                )
            except Exception as exc:
                logger.warning(
                    "Docling content extraction failed for %s (%s) — falling back to pymupdf blocks",
                    pdf_path, exc,
                )
                return self._extract_text_blocks(pdf_path)

        return self._extract_text_blocks(pdf_path)

    def _extract_text_blocks(self, pdf_path: str) -> List[ExtractedRegion]:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        doc = fitz.open(pdf_path)
        out: List[ExtractedRegion] = []

        try:
            for page_idx in range(doc.page_count):
                page_no = page_idx + 1
                page = doc[page_idx]

                try:
                    blocks = page.get_text("blocks", sort=True)
                except TypeError:
                    blocks = page.get_text("blocks")

                for block_idx, block in enumerate(blocks or []):
                    if len(block) < 7:
                        continue

                    x0, y0, x1, y1, text, _block_no, block_type = block[:7]
                    if int(block_type) != 0:
                        continue

                    cleaned = self._clean_block_text(str(text or ""))
                    if not cleaned:
                        continue

                    region = ExtractedLayoutRegion(
                        region_id=f"p{page_no}_b{block_idx}",
                        page_no=page_no,
                        region_type="text",
                    )
                    out.append(
                        ExtractedRegion(
                            region=region,
                            text=cleaned,
                            provenance={
                                "page_no": page_no,
                                "bbox": [float(x0), float(y0), float(x1), float(y1)],
                                "detector": "pymupdf_blocks",
                                "detector_confidence": 1.0,
                            },
                        )
                    )
        finally:
            doc.close()

        return out

    @staticmethod
    def _clean_block_text(text: str) -> str:
        lines = [ln.strip() for ln in (text or "").splitlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            return ""
        return "\n".join(lines).strip()

    def _extract_hierarchy(self, pdf_path: str) -> Tuple[List[SectionNode], int]:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        doc = fitz.open(pdf_path)
        total_pages = doc.page_count

        tree = self._extract_hierarchy_from_bookmarks(doc)
        source = "bookmarks"
        if not tree:
            tree = self._extract_hierarchy_from_fonts(doc, total_pages)
            source = "font-analysis"

        doc.close()

        if not tree:
            tree = [SectionNode(heading_text=Path(pdf_path).stem, heading_level=1, page_start=1)]
            source = "fallback"

        logger.info(
            "Hierarchy from %s: %d top sections (%s)",
            Path(pdf_path).name,
            len(tree),
            source,
        )
        return tree, total_pages

    def _extract_hierarchy_from_bookmarks(self, doc: Any) -> List[SectionNode]:
        toc = doc.get_toc()
        if not toc:
            return []

        flat = []
        for lvl, title, page in toc:
            t = (title or "").strip()
            if not t:
                continue
            flat.append((int(lvl), t, max(1, int(page))))
        return ItemSequencer.build_section_tree(flat)

    def _extract_hierarchy_from_fonts(self, doc: Any, total_pages: int) -> List[SectionNode]:
        all_sizes: List[float] = []
        candidates: List[Tuple[float, str, int]] = []

        num_only = re.compile(r"^[\d\s\.,\-\(\)]+$")

        for page_idx in range(total_pages):
            page_no = page_idx + 1
            page = doc[page_idx]
            try:
                blocks = page.get_text("dict", flags=7).get("blocks", [])
            except Exception:
                continue

            for block in blocks:
                lines = block.get("lines")
                if not lines:
                    continue
                for li, line in enumerate(lines):
                    spans = line.get("spans") or []
                    for si, span in enumerate(spans):
                        text = (span.get("text") or "").strip()
                        if not text:
                            continue
                        size = float(span.get("size", 0))
                        if size <= 0:
                            continue
                        all_sizes.append(round(size, 1))

                        if li == 0 and si == 0:
                            if len(text) < 160 and not num_only.fullmatch(text):
                                candidates.append((round(size, 1), text, page_no))

        if not all_sizes or not candidates:
            return []

        body_size = Counter(all_sizes).most_common(1)[0][0]
        threshold = body_size + 2.0
        filtered = [(s, t, p) for (s, t, p) in candidates if s >= threshold]
        if not filtered:
            return []

        size_levels = sorted({s for s, _, _ in filtered}, reverse=True)[:4]
        size_to_level = {s: i + 1 for i, s in enumerate(size_levels)}

        flat: List[Tuple[int, str, int]] = []
        for size, text, page in filtered:
            lvl = size_to_level.get(size, len(size_levels) or 1)
            if flat:
                prev_lvl, prev_text, prev_page = flat[-1]
                if prev_page == page and self._normalize_heading(prev_text) == self._normalize_heading(text):
                    continue
            flat.append((lvl, text, page))

        return ItemSequencer.build_section_tree(flat)

    @staticmethod
    def _normalize_heading(text: str) -> str:
        t = re.sub(r"^\s*[\d]+(?:\.[\d]+)*\.?\s*", "", text or "")
        t = re.sub(r"^\s*[A-Z](?:\.[\d]+)*\.?\s+", "", t)
        t = re.sub(r"\s+", " ", t).strip().lower()
        t = t.replace("-", "").replace("–", "").replace("—", "")
        return t

    def _count_sections(self, tree: List[Dict[str, Any]]) -> int:
        n = 0
        for node in tree:
            n += 1
            n += self._count_sections(node.get("children", []))
        return n


def _cli() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Custom modular PDF reader")
    parser.add_argument("pdf", help="Path to PDF")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for images")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    parser.add_argument("--ocr-mode", default="adaptive", choices=["adaptive", "always", "off"])
    parser.add_argument("--ocr-engine", default="rapidocr", choices=["rapidocr", "easyocr", "tesseract", "auto"])
    parser.add_argument("--include-images", action="store_true", help="Enable image extraction")
    parser.add_argument("--include-tables", action="store_true", help="Enable table extraction")
    parser.add_argument("--no-images", action="store_true", help="Disable image extraction")
    parser.add_argument("--enable-paddle-layout", action="store_true", help="Enable optional PaddleOCR layout")
    parser.add_argument("--debug-region-types", action="store_true", help="Log text/formula classification and extraction details")
    parser.add_argument("--out-json", default=None, help="Output JSON file path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    pdf_path = Path(args.pdf)
    output_dir = args.output_dir or str(pdf_path.parent / f"{pdf_path.stem}_output")
    out_json = args.out_json or str(pdf_path.parent / f"{pdf_path.stem}_parsed.json")

    cfg = CustomPdfConfig(
        enable_ocr=not args.no_ocr,
        ocr_mode=args.ocr_mode,
        ocr_engine=args.ocr_engine,
        extract_images=(args.include_images and not args.no_images),
        extract_tables=args.include_tables,
        preserve_caption_text=True,
        enable_paddle_layout=args.enable_paddle_layout,
        debug_region_types=args.debug_region_types,
    )

    reader = CustomPdfReader(cfg)
    sections = reader.read(str(pdf_path), output_dir=output_dir, skip_ocr=args.no_ocr)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(sections)} top-level sections to {out_json}")


if __name__ == "__main__":
    _cli()
