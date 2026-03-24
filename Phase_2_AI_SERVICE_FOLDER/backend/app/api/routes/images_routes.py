import logging
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.core.paths import INPUT_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["images"])


@router.get("/image")
async def get_image(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(p), media_type="image/jpeg")


@router.get("/pdf-page-image")
async def pdf_page_image(pdf_name: str, page: int):
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise HTTPException(status_code=500, detail="pdf2image not installed") from None

    rag_ready = OUTPUT_DIR / "processing" / "stage4_rag_ready"
    if not pdf_name.endswith(".pdf"):
        pdf_name = pdf_name + ".pdf"
    pdf_path = None
    if rag_ready.exists():
        for f in rag_ready.rglob("*.pdf"):
            if f.name == pdf_name:
                pdf_path = f
                break
    if pdf_path is None and INPUT_DIR.exists():
        for f in INPUT_DIR.rglob("*.pdf"):
            if f.name == pdf_name:
                pdf_path = f
                break
    if pdf_path is None:
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_name}")
    try:
        images = convert_from_path(str(pdf_path), first_page=page, last_page=page, dpi=150)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not images:
        raise HTTPException(status_code=404, detail=f"Page {page} not found")
    buf = BytesIO()
    images[0].save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
