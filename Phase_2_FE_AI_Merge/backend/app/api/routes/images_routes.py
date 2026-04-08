import logging
import os
from io import BytesIO
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import storage_user_id
from app.core.paths import workspace_paths_for_user
from app.storage import get_file_storage
from app.storage.service import S3FileStorage, parse_s3_uri

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["images"])


@router.get("/image")
def get_image(
    path: str,
    user_id: str = Depends(storage_user_id),
):
    parsed = parse_s3_uri(path)
    if parsed:
        bucket, key = parsed
        storage = get_file_storage(user_id)
        if not isinstance(storage, S3FileStorage) or bucket not in (
            storage.originals_bucket,
            storage.processed_bucket,
        ):
            raise HTTPException(status_code=403, detail="Invalid image reference")
        if not storage.can_read_object(bucket, key):
            raise HTTPException(status_code=403, detail="Object not in your storage prefix")
        try:
            body, ct = storage.read_object(bucket, key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise HTTPException(status_code=404, detail="Image not found") from e
            raise HTTPException(status_code=500, detail=str(e)) from e
        media = ct or "application/octet-stream"
        return StreamingResponse(BytesIO(body), media_type=media)

    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(p), media_type="image/jpeg")


@router.get("/pdf-page-image")
def pdf_page_image(
    pdf_name: str,
    page: int,
    user_id: str = Depends(storage_user_id),
):
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise HTTPException(status_code=500, detail="pdf2image not installed") from None

    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)
    pdf_path, cleanup = storage.resolve_pdf_path(
        pdf_name, paths.rag_ready_dir, paths.input_dir
    )
    if pdf_path is None:
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_name}")
    try:
        images = convert_from_path(str(pdf_path), first_page=page, last_page=page, dpi=150)
        if not images:
            raise HTTPException(status_code=404, detail=f"Page {page} not found")
        buf = BytesIO()
        images[0].save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if cleanup:
            try:
                os.unlink(pdf_path)
            except OSError:
                pass
