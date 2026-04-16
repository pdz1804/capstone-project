import logging
import mimetypes
import os
from io import BytesIO
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import storage_user_id
from app.api.routes.files_routes import _read_processing_file_bytes, _sanitize_processing_rel_path
from app.core.paths import workspace_paths_for_user
from app.storage import get_file_storage
from app.storage.service import S3FileStorage, parse_s3_uri

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["images"])


def _processing_rel_path_from_legacy_local_path(path: str) -> str | None:
    normalized = str(path or "").replace("\\", "/")
    marker = "/output/processing/"
    if marker not in normalized:
        return None
    rel = normalized.split(marker, 1)[1].lstrip("/")
    if not rel:
        return None
    return _sanitize_processing_rel_path(rel)


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
    if p.exists():
        media = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        return FileResponse(str(p), media_type=media)

    path_str = str(path or "")
    alt_path: Path | None = None
    if path_str.startswith("/private/var/"):
        alt_path = Path(path_str.replace("/private/var/", "/var/", 1))
    elif path_str.startswith("/var/"):
        alt_path = Path(path_str.replace("/var/", "/private/var/", 1))
    if alt_path and alt_path.exists():
        media = mimetypes.guess_type(str(alt_path))[0] or "application/octet-stream"
        return FileResponse(str(alt_path), media_type=media)

    rel_posix = _processing_rel_path_from_legacy_local_path(path_str)
    if rel_posix:
        body, media = _read_processing_file_bytes(user_id, rel_posix)
        return StreamingResponse(BytesIO(body), media_type=media)

    raise HTTPException(status_code=404, detail="Image not found")


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
