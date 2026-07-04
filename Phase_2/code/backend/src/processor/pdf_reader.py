"""Custom PDF reader (lightweight PyMuPDF text-block path).

Pipeline:
1. Build heading hierarchy (bookmarks, then font analysis fallback)
2. Extract text blocks via PyMuPDF
3. Sequence text blocks into Docling-like heading tree JSON
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import re
import shutil
import tempfile

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
    caption: Optional[str] = None
    description: Optional[str] = None
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
    # Content extraction source: "pymupdf" | "docling" | "hybrid" | "hybrid_batched"
    #   pymupdf: legacy text-blocks only (fast, no tables/formulas).
    #   docling: Docling for text+tables+formulas+pictures.
    #   hybrid : Docling first, fallback to pymupdf blocks on Docling failure.
    #   hybrid_batched: split PDF into page batches and run Docling per batch.
    content_source: str = "pymupdf"
    runtime_yaml: Optional[Dict[str, Any]] = None
    docling_batch_size: int = 8
    max_docling_concurrency: Optional[int] = None
    docling_batched_min_pages: int = 12
    enable_vlm: bool = False
    do_formula_enrichment: bool = False
    vlm_model: str = "HuggingFaceTB/SmolVLM-256M-Instruct"
    vlm_batch_size: int = 4
    vlm_page_filter: str = "visual_or_formula_pages"


@dataclass(frozen=True)
class PdfPageBatch:
    """A temporary PDF containing a contiguous 1-based page range."""

    batch_id: int
    start_page: int
    end_page: int
    pdf_path: str


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
            return self._extract_docling_regions(pdf_path, output_dir)

        if source == "hybrid":
            try:
                return self._extract_docling_regions(pdf_path, output_dir)
            except Exception as exc:
                logger.warning(
                    "Docling content extraction failed for %s (%s) — falling back to pymupdf blocks",
                    pdf_path, exc,
                )
                return self._extract_text_blocks(pdf_path)

        if source == "hybrid_batched":
            try:
                return self._extract_content_hybrid_batched(pdf_path, output_dir)
            except Exception as batched_exc:
                logger.warning(
                    "Batched Docling content extraction failed for %s (%s) — retrying unbatched Docling",
                    pdf_path, batched_exc,
                )
                try:
                    return self._extract_docling_regions(pdf_path, output_dir)
                except Exception as docling_exc:
                    logger.warning(
                        "Unbatched Docling retry failed for %s (%s) — falling back to pymupdf blocks",
                        pdf_path, docling_exc,
                    )
                    return self._extract_text_blocks(pdf_path)

        return self._extract_text_blocks(pdf_path)

    def _extract_docling_regions(
        self,
        pdf_path: str,
        output_dir: Optional[str],
        *,
        enable_vlm: Optional[bool] = None,
        do_formula_enrichment: Optional[bool] = None,
        extract_images: Optional[bool] = None,
    ) -> List[ExtractedRegion]:
        """Run the existing Docling region extractor for one PDF."""
        from .docling_remote import should_use_sagemaker_docling

        if should_use_sagemaker_docling(self.config.runtime_yaml):
            from .docling_regions import extract_regions_from_sagemaker_docling

            return extract_regions_from_sagemaker_docling(
                pdf_path,
                runtime_yaml=self.config.runtime_yaml or {},
                output_dir=output_dir,
            )

        from .docling_regions import extract_regions_from_docling

        use_vlm = self.config.enable_vlm if enable_vlm is None else bool(enable_vlm)
        use_formula = (
            self.config.do_formula_enrichment
            if do_formula_enrichment is None
            else bool(do_formula_enrichment)
        )
        return extract_regions_from_docling(
            pdf_path,
            enable_ocr=self.config.enable_ocr,
            extract_images=self.config.extract_images if extract_images is None else bool(extract_images),
            output_dir=output_dir,
            enable_vlm=use_vlm,
            do_formula_enrichment=use_formula,
            vlm_model=self.config.vlm_model,
            vlm_batch_size=self.config.vlm_batch_size,
        )

    def _extract_content_hybrid_batched(
        self,
        pdf_path: str,
        output_dir: Optional[str],
    ) -> List[ExtractedRegion]:
        """Run Docling over page batches, preserving PyMuPDF hierarchy upstream."""
        total_pages = self._get_page_count(pdf_path)
        min_pages = max(1, int(self.config.docling_batched_min_pages or 1))
        if total_pages < min_pages:
            logger.info(
                "Skipping batched Docling for %s: pages=%d below min_pages=%d",
                Path(pdf_path).name,
                total_pages,
                min_pages,
            )
            return self._extract_docling_regions(pdf_path, output_dir)

        batch_size = max(1, int(self.config.docling_batch_size or 8))
        with tempfile.TemporaryDirectory(prefix="pdf_docling_batches_") as tmp:
            batch_root = Path(tmp)
            batches = self._split_pdf_into_page_batches(pdf_path, batch_root, batch_size)
            if len(batches) <= 1:
                return self._extract_docling_regions(pdf_path, output_dir)

            max_workers = self._docling_concurrency()
            logger.info(
                "Batched Docling extractor: %s pages=%d batches=%d batch_size=%d concurrency=%d",
                Path(pdf_path).name,
                total_pages,
                len(batches),
                batch_size,
                max_workers,
            )

            all_regions: List[ExtractedRegion] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self._extract_docling_batch,
                        batch,
                        output_dir,
                        batch_root,
                    ): batch
                    for batch in batches
                }
                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        all_regions.extend(future.result())
                    except Exception as exc:
                        raise RuntimeError(
                            f"Docling failed on batch {batch.batch_id} "
                            f"pages {batch.start_page}-{batch.end_page}: {exc}"
                        ) from exc

            all_regions = self._sort_regions_for_sequencer(all_regions)
            if self.config.enable_vlm or self.config.do_formula_enrichment:
                enriched = self._extract_filtered_enrichment_regions(
                    pdf_path=pdf_path,
                    output_dir=output_dir,
                    batch_root=batch_root,
                    base_regions=all_regions,
                    total_pages=total_pages,
                    batch_size=batch_size,
                    max_workers=max_workers,
                )
                all_regions = self._merge_enriched_regions(all_regions, enriched)

            return self._sort_regions_for_sequencer(all_regions)

    def _extract_docling_batch(
        self,
        batch: PdfPageBatch,
        output_dir: Optional[str],
        batch_root: Path,
    ) -> List[ExtractedRegion]:
        batch_output_dir = None
        if output_dir:
            batch_output_dir = batch_root / f"batch_{batch.batch_id:04d}_assets"
            batch_output_dir.mkdir(parents=True, exist_ok=True)

        regions = self._extract_docling_regions(
            batch.pdf_path,
            str(batch_output_dir) if batch_output_dir else None,
            enable_vlm=False,
            do_formula_enrichment=False,
        )
        page_offset = batch.start_page - 1
        for region in regions:
            self._offset_region_page(region, batch, page_offset)
            if batch_output_dir and output_dir:
                self._promote_batch_asset(region, batch, batch_output_dir, Path(output_dir))
        return regions

    def _extract_enrichment_batch(
        self,
        batch: PdfPageBatch,
        output_dir: Optional[str],
        batch_root: Path,
    ) -> List[ExtractedRegion]:
        batch_output_dir = None
        if output_dir:
            batch_output_dir = batch_root / f"enrich_{batch.batch_id:04d}_assets"
            batch_output_dir.mkdir(parents=True, exist_ok=True)

        regions = self._extract_docling_regions(
            batch.pdf_path,
            str(batch_output_dir) if batch_output_dir else None,
            enable_vlm=self.config.enable_vlm,
            do_formula_enrichment=self.config.do_formula_enrichment,
            extract_images=self.config.extract_images or self.config.enable_vlm,
        )
        page_offset = batch.start_page - 1
        enriched: List[ExtractedRegion] = []
        for region in regions:
            if region.region.region_type not in {"formula", "image"}:
                continue
            self._offset_region_page(region, batch, page_offset)
            if batch_output_dir and output_dir:
                self._promote_batch_asset(region, batch, batch_output_dir, Path(output_dir))
            if self._is_useful_enrichment_region(region):
                enriched.append(region)
        return enriched

    def _extract_filtered_enrichment_regions(
        self,
        *,
        pdf_path: str,
        output_dir: Optional[str],
        batch_root: Path,
        base_regions: List[ExtractedRegion],
        total_pages: int,
        batch_size: int,
        max_workers: int,
    ) -> List[ExtractedRegion]:
        pages = self._select_enrichment_pages(pdf_path, base_regions, total_pages)
        if not pages:
            logger.info("Skipping Docling enrichment pass for %s: no selected pages", Path(pdf_path).name)
            return []

        batches = self._split_pdf_selected_page_batches(
            pdf_path,
            batch_root / "enrichment_batches",
            pages,
            batch_size,
        )
        logger.info(
            "Docling enrichment pass: %s pages=%d batches=%d concurrency=%d vlm=%s formula=%s",
            Path(pdf_path).name,
            len(pages),
            len(batches),
            max_workers,
            self.config.enable_vlm,
            self.config.do_formula_enrichment,
        )

        out: List[ExtractedRegion] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {
                executor.submit(
                    self._extract_enrichment_batch,
                    batch,
                    output_dir,
                    batch_root,
                ): batch
                for batch in batches
            }
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    out.extend(future.result())
                except Exception as exc:
                    logger.warning(
                        "Docling enrichment failed on batch %d pages %d-%d: %s",
                        batch.batch_id,
                        batch.start_page,
                        batch.end_page,
                        exc,
                    )
        return out

    def _offset_region_page(
        self,
        region: ExtractedRegion,
        batch: PdfPageBatch,
        page_offset: int,
    ) -> None:
        local_page_no = int(getattr(region.region, "page_no", 1) or 1)
        global_page_no = local_page_no + page_offset
        old_region_id = str(region.region.region_id or f"region_{id(region)}")

        region.region.page_no = global_page_no
        region.region.region_id = f"b{batch.batch_id:04d}_p{global_page_no}_{old_region_id}"
        region.provenance = region.provenance or {}
        region.provenance["page_no"] = global_page_no
        region.provenance["docling_batch_id"] = batch.batch_id
        region.provenance["docling_batch_start_page"] = batch.start_page
        region.provenance["docling_batch_end_page"] = batch.end_page

    def _promote_batch_asset(
        self,
        region: ExtractedRegion,
        batch: PdfPageBatch,
        batch_output_dir: Path,
        output_dir: Path,
    ) -> None:
        if not region.image_rel_path:
            return

        rel = str(region.image_rel_path).replace("\\", "/").lstrip("/")
        if ".." in rel or rel.startswith("/"):
            logger.warning("Skipping unsafe batched Docling asset path: %s", region.image_rel_path)
            return

        source = batch_output_dir / rel
        if not source.exists():
            return

        dest_dir = output_dir / "images"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"batch_{batch.batch_id:04d}_{source.name}"
        dest = dest_dir / dest_name
        shutil.copy2(source, dest)
        region.image_rel_path = f"images/{dest_name}"

    def _docling_concurrency(self) -> int:
        configured = self.config.max_docling_concurrency
        if configured is not None:
            return max(1, int(configured))

        from .docling_remote import should_use_sagemaker_docling

        if should_use_sagemaker_docling(self.config.runtime_yaml):
            return 4
        if self.config.enable_vlm or self.config.do_formula_enrichment:
            return 1
        return 1

    @staticmethod
    def _get_page_count(pdf_path: str) -> int:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        with fitz.open(pdf_path) as doc:
            return int(doc.page_count)

    @staticmethod
    def _split_pdf_into_page_batches(
        pdf_path: str,
        output_dir: Path,
        batch_size: int,
    ) -> List[PdfPageBatch]:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        batches: List[PdfPageBatch] = []

        with fitz.open(pdf_path) as src:
            total_pages = int(src.page_count)
            for batch_id, start_idx in enumerate(range(0, total_pages, batch_size)):
                end_idx = min(start_idx + batch_size, total_pages)
                batch_doc = fitz.open()
                try:
                    batch_doc.insert_pdf(src, from_page=start_idx, to_page=end_idx - 1)
                    batch_path = output_dir / (
                        f"batch_{batch_id:04d}_p{start_idx + 1}_to_{end_idx}.pdf"
                    )
                    batch_doc.save(str(batch_path))
                finally:
                    batch_doc.close()

                batches.append(
                    PdfPageBatch(
                        batch_id=batch_id,
                        start_page=start_idx + 1,
                        end_page=end_idx,
                        pdf_path=str(batch_path),
                    )
                )

        return batches

    @staticmethod
    def _split_pdf_selected_page_batches(
        pdf_path: str,
        output_dir: Path,
        selected_pages: List[int],
        batch_size: int,
    ) -> List[PdfPageBatch]:
        pages = sorted({int(p) for p in selected_pages if int(p) > 0})
        if not pages:
            return []

        ranges: List[Tuple[int, int]] = []
        start = prev = pages[0]
        for page_no in pages[1:]:
            if page_no == prev + 1 and (page_no - start + 1) <= batch_size:
                prev = page_no
                continue
            ranges.append((start, prev))
            start = prev = page_no
        ranges.append((start, prev))

        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        batches: List[PdfPageBatch] = []
        with fitz.open(pdf_path) as src:
            for batch_id, (start_page, end_page) in enumerate(ranges):
                batch_doc = fitz.open()
                try:
                    batch_doc.insert_pdf(src, from_page=start_page - 1, to_page=end_page - 1)
                    batch_path = output_dir / (
                        f"enrich_{batch_id:04d}_p{start_page}_to_{end_page}.pdf"
                    )
                    batch_doc.save(str(batch_path))
                finally:
                    batch_doc.close()
                batches.append(
                    PdfPageBatch(
                        batch_id=batch_id,
                        start_page=start_page,
                        end_page=end_page,
                        pdf_path=str(batch_path),
                    )
                )
        return batches

    def _select_enrichment_pages(
        self,
        pdf_path: str,
        base_regions: List[ExtractedRegion],
        total_pages: int,
    ) -> List[int]:
        mode = (self.config.vlm_page_filter or "visual_or_formula_pages").strip().lower()
        if mode in {"all", "all_pages"}:
            return list(range(1, total_pages + 1))

        selected = set(self._detect_visual_pages(pdf_path))
        table_counts: Dict[int, int] = {}
        for region in base_regions:
            page_no = int((region.provenance or {}).get("page_no") or region.region.page_no or 1)
            if region.region.region_type in {"formula", "image"}:
                selected.add(page_no)
            if region.region.region_type == "table":
                table_counts[page_no] = table_counts.get(page_no, 0) + 1
        for page_no, count in table_counts.items():
            if count >= 2:
                selected.add(page_no)
        return sorted(p for p in selected if 1 <= p <= total_pages)

    @staticmethod
    def _detect_visual_pages(pdf_path: str) -> List[int]:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("PyMuPDF is required: pip install pymupdf") from exc

        pages: List[int] = []
        with fitz.open(pdf_path) as doc:
            for page_idx in range(doc.page_count):
                page = doc[page_idx]
                has_visual = bool(page.get_images(full=True))
                if not has_visual:
                    try:
                        has_visual = bool(page.get_drawings())
                    except Exception:
                        has_visual = False
                if not has_visual:
                    try:
                        blocks = page.get_text("blocks")
                    except Exception:
                        blocks = []
                    has_visual = any(len(block) >= 7 and int(block[6]) != 0 for block in blocks or [])
                if has_visual:
                    pages.append(page_idx + 1)
        return pages

    @staticmethod
    def _is_useful_enrichment_region(region: ExtractedRegion) -> bool:
        if region.region.region_type == "formula":
            return bool((region.latex or region.text or "").strip())
        if region.region.region_type == "image":
            return bool(
                (region.description or "").strip()
                or (region.caption or "").strip()
                or (region.image_rel_path and region.image_md5)
            )
        return False

    def _merge_enriched_regions(
        self,
        base_regions: List[ExtractedRegion],
        enriched_regions: List[ExtractedRegion],
    ) -> List[ExtractedRegion]:
        seen = {self._region_dedupe_key(region) for region in base_regions}
        merged = list(base_regions)
        for region in enriched_regions:
            if self._merge_image_description_into_existing(merged, region):
                continue
            key = self._region_dedupe_key(region)
            if key in seen:
                continue
            seen.add(key)
            merged.append(region)
        return merged

    @staticmethod
    def _merge_image_description_into_existing(
        regions: List[ExtractedRegion],
        enriched: ExtractedRegion,
    ) -> bool:
        if enriched.region.region_type != "image":
            return False
        page_no = int((enriched.provenance or {}).get("page_no") or enriched.region.page_no or 1)
        image_key = enriched.image_md5 or enriched.image_rel_path
        if not image_key:
            return False
        for region in regions:
            if region.region.region_type != "image":
                continue
            existing_page = int((region.provenance or {}).get("page_no") or region.region.page_no or 1)
            existing_key = region.image_md5 or region.image_rel_path
            if existing_page != page_no or existing_key != image_key:
                continue
            if enriched.description and not region.description:
                region.description = enriched.description
            if enriched.caption and not region.caption:
                region.caption = enriched.caption
            return True
        return False

    @staticmethod
    def _region_dedupe_key(region: ExtractedRegion) -> Tuple[Any, ...]:
        page_no = int((region.provenance or {}).get("page_no") or region.region.page_no or 1)
        kind = region.region.region_type
        text = " ".join((region.latex or region.description or region.caption or region.text or "").split())
        image_key = region.image_md5 or region.image_rel_path or ""
        return (kind, page_no, text[:500], image_key)

    @staticmethod
    def _sort_regions_for_sequencer(regions: List[ExtractedRegion]) -> List[ExtractedRegion]:
        def _bbox(region: ExtractedRegion) -> List[float]:
            bbox = (region.provenance or {}).get("bbox") or [0.0, 0.0, 0.0, 0.0]
            if not isinstance(bbox, list) or len(bbox) < 2:
                return [0.0, 0.0, 0.0, 0.0]
            return bbox

        return sorted(
            regions,
            key=lambda r: (
                int(getattr(r.region, "page_no", 1) or 1),
                -float(_bbox(r)[1] or 0.0),
                float(_bbox(r)[0] or 0.0),
                str(getattr(r.region, "region_id", "")),
            ),
        )

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
    parser.add_argument(
        "--content-source",
        choices=["pymupdf", "docling", "hybrid", "hybrid_batched"],
        default="pymupdf",
        help="Content source for raw regions.",
    )
    parser.add_argument("--docling-batch-size", type=int, default=8, help="Pages per Docling batch.")
    parser.add_argument(
        "--max-docling-concurrency",
        type=int,
        default=None,
        help="Maximum concurrent Docling batch conversions.",
    )
    parser.add_argument(
        "--docling-batched-min-pages",
        type=int,
        default=12,
        help="Minimum PDF page count before hybrid_batched splits work.",
    )
    parser.add_argument("--enable-vlm", action="store_true", help="Enable Docling VLM picture descriptions.")
    parser.add_argument("--enable-formula-enrichment", action="store_true", help="Enable Docling formula enrichment.")
    parser.add_argument(
        "--vlm-model",
        default="HuggingFaceTB/SmolVLM-256M-Instruct",
        help="Hugging Face repo id for Docling VLM picture descriptions.",
    )
    parser.add_argument("--vlm-batch-size", type=int, default=4, help="Docling VLM internal batch size.")
    parser.add_argument(
        "--vlm-page-filter",
        default="visual_or_formula_pages",
        choices=["visual_or_formula_pages", "all_pages"],
        help="Page selection policy for the enrichment pass.",
    )
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
        content_source=args.content_source,
        docling_batch_size=args.docling_batch_size,
        max_docling_concurrency=args.max_docling_concurrency,
        docling_batched_min_pages=args.docling_batched_min_pages,
        enable_vlm=args.enable_vlm,
        do_formula_enrichment=args.enable_formula_enrichment,
        vlm_model=args.vlm_model,
        vlm_batch_size=args.vlm_batch_size,
        vlm_page_filter=args.vlm_page_filter,
    )

    reader = CustomPdfReader(cfg)
    sections = reader.read(str(pdf_path), output_dir=output_dir, skip_ocr=args.no_ocr)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(sections)} top-level sections to {out_json}")


if __name__ == "__main__":
    _cli()
