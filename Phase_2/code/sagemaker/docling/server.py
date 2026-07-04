"""
SageMaker-compatible Docling document processing server.

Request contract used by backend/src/processor/docling_remote.py:
{
  "operation": "process-document",
  "filename": "sample.pdf",
  "content_base64": "..."
}

Processing defaults are intentionally conservative (no VLM, no image/table export)
to match backend/config/default.yaml. Override via env:
  DOCLING_ENABLE_VLM=true
  DOCLING_EXPORT_IMAGES=true
  DOCLING_EXPORT_TABLES=true
  DOCLING_OCR_ENGINE=rapidocr|tesseract|easyocr
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger("docling-sagemaker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_converter = None
_load_time_s = 0.0


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


class InvocationRequest(BaseModel):
    operation: str
    filename: str = "document.pdf"
    content_base64: str = ""
    return_regions: bool = False


def _extract_markdown(doc_or_result) -> str:
    doc = getattr(doc_or_result, "document", doc_or_result)
    for attr in ("export_to_markdown", "to_markdown"):
        fn = getattr(doc, attr, None)
        if callable(fn):
            text = fn()
            if isinstance(text, str) and text.strip():
                return text
    text = getattr(doc_or_result, "markdown", "")
    if isinstance(text, str) and text.strip():
        return text
    raise RuntimeError("Docling conversion produced empty markdown output")


def _first_prov(item: Any) -> tuple[int, list[float]]:
    prov = getattr(item, "prov", None) or []
    if not prov:
        return 1, [0.0, 0.0, 0.0, 0.0]
    p0 = prov[0]
    page_no = int(getattr(p0, "page_no", 1) or 1)
    bbox_obj = getattr(p0, "bbox", None)
    if bbox_obj is None:
        return page_no, [0.0, 0.0, 0.0, 0.0]
    return page_no, [
        float(getattr(bbox_obj, "l", 0.0) or 0.0),
        float(getattr(bbox_obj, "t", 0.0) or 0.0),
        float(getattr(bbox_obj, "r", 0.0) or 0.0),
        float(getattr(bbox_obj, "b", 0.0) or 0.0),
    ]


def _extract_regions(doc_or_result) -> List[Dict[str, Any]]:
    from docling_core.types.doc.labels import DocItemLabel

    doc = getattr(doc_or_result, "document", doc_or_result)
    text_labels = {
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

    regions: List[Dict[str, Any]] = []
    for item, _level in doc.iterate_items():
        label = getattr(item, "label", None)
        page_no, bbox = _first_prov(item)
        region_id = f"p{page_no}_{getattr(item, 'self_ref', id(item))}"

        if label in text_labels:
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            region_type = "text"
            payload_text = text
            markdown_table = None
            latex = None
        elif label == DocItemLabel.TABLE:
            try:
                payload_text = (item.export_to_markdown(doc=doc) or "").strip()
            except Exception:
                payload_text = ""
            if not payload_text:
                continue
            region_type = "table"
            markdown_table = payload_text
            latex = None
        elif label == DocItemLabel.FORMULA:
            payload_text = (getattr(item, "text", "") or "").strip()
            if not payload_text:
                continue
            region_type = "formula"
            markdown_table = None
            latex = payload_text
        else:
            continue

        regions.append(
            {
                "region_id": region_id,
                "region_type": region_type,
                "page_no": page_no,
                "bbox": bbox,
                "text": payload_text,
                "markdown_table": markdown_table,
                "latex": latex,
                "image_rel_path": None,
                "image_md5": None,
                "ocr_used": False,
                "provenance": {
                    "page_no": page_no,
                    "bbox": bbox,
                    "detector": "docling_sagemaker",
                    "docling_label": str(label),
                },
            }
        )
    regions.sort(key=lambda r: (int(r.get("page_no") or 1), -float((r.get("bbox") or [0, 0, 0, 0])[1])))
    return regions


def _load_converter() -> None:
    global _converter, _load_time_s
    started = time.time()
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    enable_vlm = _truthy_env("DOCLING_ENABLE_VLM", default=False)
    enable_ocr = _truthy_env("DOCLING_ENABLE_OCR", default=True)
    export_images = _truthy_env("DOCLING_EXPORT_IMAGES", default=False)
    export_tables = _truthy_env("DOCLING_EXPORT_TABLES", default=False)
    ocr_engine = os.getenv("DOCLING_OCR_ENGINE", "rapidocr").strip().lower()

    logger.info(
        "Docling config: enable_vlm=%s enable_ocr=%s export_images=%s export_tables=%s ocr_engine=%s",
        enable_vlm, enable_ocr, export_images, export_tables, ocr_engine,
    )

    try:
        ocr_options = None
        if enable_ocr:
            if ocr_engine == "rapidocr":
                from docling.datamodel.pipeline_options import RapidOcrOptions
                ocr_options = RapidOcrOptions()
            elif ocr_engine == "easyocr":
                from docling.datamodel.pipeline_options import EasyOcrOptions
                ocr_options = EasyOcrOptions()

        pdf_options_kwargs = {
            "do_ocr": enable_ocr,
            "do_table_structure": export_tables,
            "generate_picture_images": export_images,
            "generate_page_images": export_images,
            "generate_table_images": export_tables,
            "do_picture_classification": enable_vlm,
            "do_picture_description": enable_vlm,
            "images_scale": 2.0,
        }
        if ocr_options is not None:
            pdf_options_kwargs["ocr_options"] = ocr_options

        pdf_opts = PdfPipelineOptions(**pdf_options_kwargs)

        try:
            from docling.document_converter import FormatOption
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
            _converter = DocumentConverter(
                format_options={InputFormat.PDF: FormatOption(pipeline_cls=StandardPdfPipeline, pipeline_options=pdf_opts)}
            )
        except Exception:
            _converter = DocumentConverter()
    except Exception as exc:
        logger.warning("Enhanced Docling setup failed (%s), falling back to default converter", exc)
        _converter = DocumentConverter()

    _load_time_s = time.time() - started
    logger.info("Docling converter loaded in %.2fs", _load_time_s)


def _process_document(filename: str, content_base64: str, *, return_regions: bool = False) -> dict:
    if not content_base64:
        raise HTTPException(status_code=400, detail="content_base64 is required")

    try:
        raw = base64.b64decode(content_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}") from exc

    suffix = Path(filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    try:
        result = _converter.convert(str(tmp_path))
        markdown = _extract_markdown(result)
        data = {"markdown": markdown, "additional_files": {}}
        if return_regions:
            data["regions"] = _extract_regions(result)
        return data
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


app = FastAPI(title="Docling SageMaker Server", version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    _load_converter()


@app.get("/ping")
async def ping():
    return Response(status_code=200 if _converter is not None else 503)


@app.get("/health")
async def health():
    return {
        "status": "healthy" if _converter is not None else "not_ready",
        "model": "docling",
        "load_time_s": round(_load_time_s, 3),
        "config": {
            "enable_vlm": _truthy_env("DOCLING_ENABLE_VLM", default=False),
            "enable_ocr": _truthy_env("DOCLING_ENABLE_OCR", default=True),
            "export_images": _truthy_env("DOCLING_EXPORT_IMAGES", default=False),
            "export_tables": _truthy_env("DOCLING_EXPORT_TABLES", default=False),
            "ocr_engine": os.getenv("DOCLING_OCR_ENGINE", "rapidocr"),
        },
    }


@app.post("/invocations")
async def invocations(req: InvocationRequest = Body(...)):
    op = req.operation.strip().lower()
    if op == "health":
        return await health()
    if op != "process-document":
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {req.operation}")

    if _converter is None:
        raise HTTPException(status_code=503, detail="Docling converter not loaded")

    started = time.time()
    data = _process_document(req.filename, req.content_base64, return_regions=req.return_regions)
    data["inference_time_ms"] = round((time.time() - started) * 1000, 1)
    return data
