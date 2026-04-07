"""
SageMaker-compatible Docling document processing server.

Request contract used by backend/src/processor/docling_remote.py:
{
  "operation": "process-document",
  "filename": "sample.pdf",
  "content_base64": "..."
}
"""

from __future__ import annotations

import base64
import logging
import tempfile
import time
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger("docling-sagemaker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_converter = None
_load_time_s = 0.0


class InvocationRequest(BaseModel):
    operation: str
    filename: str = "document.pdf"
    content_base64: str = ""


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


def _load_converter() -> None:
    global _converter, _load_time_s
    started = time.time()
    from docling.document_converter import DocumentConverter

    _converter = DocumentConverter()
    _load_time_s = time.time() - started
    logger.info("Docling converter loaded in %.2fs", _load_time_s)


def _process_document(filename: str, content_base64: str) -> dict:
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
        return {"markdown": markdown, "additional_files": {}}
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
    data = _process_document(req.filename, req.content_base64)
    data["inference_time_ms"] = round((time.time() - started) * 1000, 1)
    return data
