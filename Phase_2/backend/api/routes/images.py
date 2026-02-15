"""
Image serving routes: raw images and PDF page rendering.
"""

import logging
from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from shared import INPUT_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["images"])


@router.get("/image")
async def get_image(path: str):
    """Get image by path."""
    try:
        file_path = Path(path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(str(file_path), media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Failed to serve image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf-page-image")
async def get_pdf_page_image(pdf_name: str, page: int):
    """
    Render a specific page from a PDF as an image.

    Args:
        pdf_name: Name of the PDF file (without extension or with .pdf)
        page: Page number (1-indexed)
    """
    try:
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="pdf2image not installed. Run: pip install pdf2image"
            )

        rag_ready_dir = OUTPUT_DIR / "processing" / "stage4_rag_ready"

        if not pdf_name.endswith('.pdf'):
            pdf_name = pdf_name + '.pdf'

        pdf_path = None

        if rag_ready_dir.exists():
            for f in rag_ready_dir.rglob("*.pdf"):
                if f.name == pdf_name:
                    pdf_path = f
                    break

        if not pdf_path and INPUT_DIR.exists():
            for f in INPUT_DIR.rglob("*.pdf"):
                if f.name == pdf_name:
                    pdf_path = f
                    break

        if not pdf_path:
            raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_name}")

        try:
            images = convert_from_path(
                str(pdf_path),
                first_page=page,
                last_page=page,
                dpi=150
            )
        except Exception as e:
            logger.error(f"pdf2image conversion failed: {e}")
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {str(e)}")

        if not images:
            raise HTTPException(status_code=404, detail=f"Page {page} not found in PDF")

        img_byte_arr = BytesIO()
        images[0].save(img_byte_arr, format='PNG', optimize=True)
        img_byte_arr.seek(0)

        return StreamingResponse(img_byte_arr, media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render PDF page: {e}")
        raise HTTPException(status_code=500, detail=str(e))
