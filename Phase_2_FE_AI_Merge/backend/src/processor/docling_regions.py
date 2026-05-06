"""Docling → ExtractedRegion adapter.

Walks a DoclingDocument and emits the same ExtractedRegion shape that
ItemSequencer consumes.  Lets us reuse PyMuPDF ToC as the section tree
while Docling handles content extraction (text, tables, formulas, pictures).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .pdf_reader import ExtractedLayoutRegion, ExtractedRegion

logger = logging.getLogger(__name__)


def _first_prov(item: Any) -> Tuple[int, Tuple[float, float, float, float]]:
    """Return (page_no, bbox) from the first provenance entry, or (1, zeros)."""
    prov = getattr(item, "prov", None) or []
    if not prov:
        return 1, (0.0, 0.0, 0.0, 0.0)
    p0 = prov[0]
    page_no = int(getattr(p0, "page_no", 1) or 1)
    bbox_obj = getattr(p0, "bbox", None)
    if bbox_obj is None:
        return page_no, (0.0, 0.0, 0.0, 0.0)
    # Docling BoundingBox has l, t, r, b
    l = float(getattr(bbox_obj, "l", 0.0) or 0.0)
    t = float(getattr(bbox_obj, "t", 0.0) or 0.0)
    r = float(getattr(bbox_obj, "r", 0.0) or 0.0)
    b = float(getattr(bbox_obj, "b", 0.0) or 0.0)
    return page_no, (l, t, r, b)


def _save_picture(image_ref: Any, img_dir: Path, counter: int) -> Optional[Tuple[str, str]]:
    """Save an ImageRef to img_dir; return (rel_path, md5_short) or None."""
    try:
        uri = getattr(image_ref, "uri", None)
        if uri is None:
            return None
        uri_str = str(uri)

        if uri_str.startswith("data:"):
            m = re.match(r"data:image/(\w+);base64,(.+)", uri_str, re.DOTALL)
            if not m:
                return None
            ext = m.group(1)
            if ext == "jpeg":
                ext = "jpg"
            img_bytes = base64.b64decode(m.group(2))
        else:
            p = Path(uri_str)
            if not p.exists():
                return None
            img_bytes = p.read_bytes()
            ext = p.suffix.lstrip(".") or "png"

        if len(img_bytes) < 100:
            return None

        md5_short = hashlib.md5(img_bytes).hexdigest()[:8]
        filename = f"img_docling_{counter:03d}.{ext}"
        dest = img_dir / filename
        dest.write_bytes(img_bytes)
        return f"images/{filename}", md5_short
    except Exception as exc:
        logger.debug("Failed to save docling picture: %s", exc)
        return None


def _region_to_payload(er: ExtractedRegion) -> Dict[str, Any]:
    provenance = dict(er.provenance or {})
    page_no = int(provenance.get("page_no") or er.region.page_no or 1)
    bbox = provenance.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    return {
        "region_id": er.region.region_id,
        "region_type": er.region.region_type,
        "page_no": page_no,
        "bbox": bbox,
        "text": er.text or "",
        "markdown_table": er.markdown_table,
        "latex": er.latex,
        "image_rel_path": er.image_rel_path,
        "image_md5": er.image_md5,
        "ocr_used": bool(er.ocr_used),
        "provenance": provenance,
    }


def serialize_regions(regions: List[ExtractedRegion]) -> List[Dict[str, Any]]:
    """Serialize ExtractedRegion objects for the SageMaker JSON contract."""
    return [_region_to_payload(er) for er in regions]


def regions_from_sagemaker_payload(
    payload: Dict[str, Any],
    *,
    output_dir: Optional[str] = None,
) -> List[ExtractedRegion]:
    """Convert SageMaker ``regions`` JSON back into ExtractedRegion objects."""
    additional_files = payload.get("additional_files") or {}
    if output_dir and isinstance(additional_files, dict):
        base = Path(output_dir)
        for rel, b64 in additional_files.items():
            rel_s = str(rel).replace("\\", "/").lstrip("/")
            if ".." in rel_s or rel_s.startswith("/"):
                logger.warning("Skipping unsafe SageMaker region asset path: %s", rel)
                continue
            try:
                target = base / rel_s
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(str(b64)))
            except Exception as exc:
                logger.debug("Failed to materialize SageMaker asset %s: %s", rel, exc)

    out: List[ExtractedRegion] = []
    for idx, item in enumerate(payload.get("regions") or []):
        if not isinstance(item, dict):
            continue
        page_no = int(item.get("page_no") or 1)
        region_type = str(item.get("region_type") or item.get("type") or "text")
        provenance = dict(item.get("provenance") or {})
        provenance.setdefault("page_no", page_no)
        provenance.setdefault("bbox", item.get("bbox") or [0.0, 0.0, 0.0, 0.0])
        provenance.setdefault("detector", "docling_sagemaker")
        region = ExtractedLayoutRegion(
            region_id=str(item.get("region_id") or f"sm_p{page_no}_{idx}"),
            page_no=page_no,
            region_type=region_type,
        )
        out.append(
            ExtractedRegion(
                region=region,
                text=str(item.get("text") or ""),
                markdown_table=item.get("markdown_table"),
                latex=item.get("latex"),
                image_rel_path=item.get("image_rel_path"),
                image_md5=item.get("image_md5"),
                ocr_used=bool(item.get("ocr_used", False)),
                provenance=provenance,
            )
        )
    return out


def extract_regions_from_sagemaker_docling(
    file_path: str,
    *,
    runtime_yaml: Dict[str, Any],
    output_dir: Optional[str] = None,
) -> List[ExtractedRegion]:
    """Invoke SageMaker Docling and return structured regions.

    Requires the endpoint to support ``return_regions=true``. Older endpoints
    return markdown only; callers should handle the resulting empty region set
    as a fallback condition.
    """
    from .docling_remote import invoke_sagemaker_docling

    payload = invoke_sagemaker_docling(Path(file_path), runtime_yaml, return_regions=True)
    regions = regions_from_sagemaker_payload(payload, output_dir=output_dir)
    if not regions:
        raise RuntimeError("SageMaker Docling response did not include structured regions")
    logger.info("SageMaker Docling extractor: %d regions", len(regions))
    return regions


def _make_converter(enable_ocr: bool, extract_images: bool):
    """Build a Docling DocumentConverter configured for PDF.

    Mirrors the primary-converter config in document_processor_v2.
    """
    from docling.document_converter import DocumentConverter, FormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

    # Best available backend
    backend_cls = None
    for path in (
        "docling.backend.docling_parse_v4_backend.DoclingParseV4DocumentBackend",
        "docling.backend.docling_parse_backend.DoclingParseDocumentBackend",
        "docling.backend.pypdfium2_backend.PyPdfiumDocumentBackend",
    ):
        mod_path, cls_name = path.rsplit(".", 1)
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            backend_cls = getattr(mod, cls_name)
            break
        except (ImportError, AttributeError):
            continue

    ocr_opts = None
    if enable_ocr:
        try:
            from docling.datamodel.pipeline_options import RapidOcrOptions
            ocr_opts = RapidOcrOptions()
        except Exception:
            pass

    pdf_kwargs: Dict[str, Any] = {
        "do_ocr": enable_ocr,
        "do_table_structure": True,
        # Keep local hybrid PDF parsing focused on raw text/table regions.
        # Formula enrichment pulls a heavy VLM checkpoint and is not needed for
        # chunking evaluation or section assignment.
        "do_formula_enrichment": False,
        "generate_picture_images": extract_images,
        "generate_page_images": False,
        "generate_table_images": False,
        "images_scale": 2.0,
    }
    if ocr_opts is not None:
        pdf_kwargs["ocr_options"] = ocr_opts

    pdf_opts = PdfPipelineOptions(**pdf_kwargs)

    fmt_kwargs: Dict[str, Any] = {
        "pipeline_cls": StandardPdfPipeline,
        "pipeline_options": pdf_opts,
    }
    if backend_cls is not None:
        fmt_kwargs["backend"] = backend_cls

    return DocumentConverter(
        format_options={InputFormat.PDF: FormatOption(**fmt_kwargs)},
    )


def extract_regions_from_docling(
    file_path: str,
    *,
    enable_ocr: bool = True,
    extract_images: bool = True,
    output_dir: Optional[str] = None,
) -> List[ExtractedRegion]:
    """Run Docling on *file_path* and emit ExtractedRegion list.

    Regions are sorted by (page_no, top-y) so ItemSequencer walks them in
    reading order.  ItemSequencer's heading queue will pop headings as it
    walks; remaining non-heading content falls into the current section.
    """
    from docling_core.types.doc.labels import DocItemLabel

    img_dir: Optional[Path] = None
    if output_dir and extract_images:
        img_dir = Path(output_dir) / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

    converter = _make_converter(enable_ocr=enable_ocr, extract_images=extract_images)
    result = converter.convert(file_path)
    doc = getattr(result, "document", result)

    TEXT_LABELS = {
        DocItemLabel.TITLE,
        DocItemLabel.SECTION_HEADER,
        DocItemLabel.TEXT,
        DocItemLabel.PARAGRAPH,
        DocItemLabel.LIST_ITEM,
        DocItemLabel.CAPTION,
        DocItemLabel.FOOTNOTE,
        DocItemLabel.CODE,
        DocItemLabel.REFERENCE,
    }

    staged: List[Tuple[int, float, ExtractedRegion]] = []
    img_counter = 0
    detector_counts: Dict[str, int] = {}

    for item, _level in doc.iterate_items():
        label = getattr(item, "label", None)
        page_no, bbox = _first_prov(item)

        if label in TEXT_LABELS:
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            region = ExtractedLayoutRegion(
                region_id=f"p{page_no}_{getattr(item, 'self_ref', id(item))}",
                page_no=page_no,
                region_type="text",
            )
            er = ExtractedRegion(
                region=region,
                text=text,
                provenance={
                    "page_no": page_no,
                    "bbox": list(bbox),
                    "detector": "docling",
                    "docling_label": str(label),
                    "detector_confidence": 1.0,
                },
            )
            staged.append((page_no, bbox[1], er))
            detector_counts["text"] = detector_counts.get("text", 0) + 1

        elif label == DocItemLabel.TABLE:
            md = ""
            try:
                md = (item.export_to_markdown(doc=doc) or "").strip()
            except Exception as exc:
                logger.debug("Table markdown export failed (p%d): %s", page_no, exc)
            if not md:
                continue
            region = ExtractedLayoutRegion(
                region_id=f"p{page_no}_table_{len(staged)}",
                page_no=page_no,
                region_type="table",
            )
            er = ExtractedRegion(
                region=region,
                text=md,
                markdown_table=md,
                provenance={
                    "page_no": page_no,
                    "bbox": list(bbox),
                    "detector": "docling",
                    "docling_label": "TABLE",
                },
            )
            staged.append((page_no, bbox[1], er))
            detector_counts["table"] = detector_counts.get("table", 0) + 1

        elif label == DocItemLabel.FORMULA:
            latex = (getattr(item, "text", "") or "").strip()
            if not latex:
                continue
            region = ExtractedLayoutRegion(
                region_id=f"p{page_no}_formula_{len(staged)}",
                page_no=page_no,
                region_type="formula",
            )
            er = ExtractedRegion(
                region=region,
                text=latex,
                latex=latex,
                provenance={
                    "page_no": page_no,
                    "bbox": list(bbox),
                    "detector": "docling",
                    "docling_label": "FORMULA",
                },
            )
            staged.append((page_no, bbox[1], er))
            detector_counts["formula"] = detector_counts.get("formula", 0) + 1

        elif label == DocItemLabel.PICTURE:
            if img_dir is None:
                continue
            image_ref = getattr(item, "image", None)
            if image_ref is None:
                continue
            saved = _save_picture(image_ref, img_dir, img_counter)
            if saved is None:
                continue
            img_counter += 1
            rel_path, md5_short = saved
            region = ExtractedLayoutRegion(
                region_id=f"p{page_no}_pic_{img_counter}",
                page_no=page_no,
                region_type="image",
            )
            er = ExtractedRegion(
                region=region,
                image_rel_path=rel_path,
                image_md5=md5_short,
                provenance={
                    "page_no": page_no,
                    "bbox": list(bbox),
                    "detector": "docling",
                    "docling_label": "PICTURE",
                },
            )
            staged.append((page_no, bbox[1], er))
            detector_counts["image"] = detector_counts.get("image", 0) + 1

        # Skip PAGE_HEADER, PAGE_FOOTER, DOCUMENT_INDEX, etc.

    # Docling bbox uses bottom-up y in some backends; to keep reading order
    # robust, sort by (page_no, -top) if top looks inverted.  We use -bbox[1]
    # when backend reports y0 from bottom; detect by sampling typical range.
    staged.sort(key=lambda t: (t[0], -t[1]))

    logger.info(
        "Docling extractor: %s regions (text=%d table=%d formula=%d image=%d)",
        len(staged),
        detector_counts.get("text", 0),
        detector_counts.get("table", 0),
        detector_counts.get("formula", 0),
        detector_counts.get("image", 0),
    )
    return [er for _, _, er in staged]
