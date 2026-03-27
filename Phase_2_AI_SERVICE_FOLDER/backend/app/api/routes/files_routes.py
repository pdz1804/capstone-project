import json
import logging
import mimetypes
import os
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import storage_user_id
from app.api.schemas import FileDeleteRequest
from app.core.paths import (
    ensure_data_dirs,
    merged_runtime_settings,
    qdrant_collection_names_for_user,
    workspace_paths_for_user,
)
from app.services.processed_documents_service import build_processed_documents_snapshot
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["files"])

_MAX_PROCESSED_FILE_BYTES = int(os.getenv("MAX_PROCESSED_FILE_PREVIEW_BYTES", str(50 * 1024 * 1024)))


def _sanitize_processing_rel_path(raw: str) -> str:
    s = (raw or "").strip().replace("\\", "/").lstrip("/")
    if not s or len(s) > 2048:
        raise HTTPException(status_code=400, detail="Invalid rel_path")
    parts = s.split("/")
    if ".." in parts or "" in parts:
        raise HTTPException(status_code=400, detail="Invalid rel_path")
    return s


def _read_processing_file_bytes(user_id: str, rel_posix: str) -> Tuple[bytes, str]:
    """Return (body, media_type) for a file under the user's processing tree (local or S3)."""
    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)
    guessed, _ = mimetypes.guess_type(rel_posix)
    default_media = guessed or "application/octet-stream"

    if isinstance(storage, S3FileStorage):
        key = storage._key_processing(rel_posix)
        if not storage.can_read_object(storage.processed_bucket, key):
            raise HTTPException(status_code=403, detail="Object not in your processing prefix")
        try:
            head = storage._client.head_object(Bucket=storage.processed_bucket, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise HTTPException(status_code=404, detail="File not found") from e
            raise HTTPException(status_code=500, detail=str(e)) from e
        sz = int(head.get("ContentLength") or 0)
        if sz > _MAX_PROCESSED_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large for preview (max {_MAX_PROCESSED_FILE_BYTES} bytes)",
            )
        try:
            body, ct = storage.read_object(storage.processed_bucket, key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise HTTPException(status_code=404, detail="File not found") from e
            raise HTTPException(status_code=500, detail=str(e)) from e
        media = (ct or "").split(";")[0].strip() or default_media
        return body, media

    root = paths.processing_dir.resolve()
    target = (root / Path(*rel_posix.split("/"))).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside processing directory") from None
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    sz = target.stat().st_size
    if sz > _MAX_PROCESSED_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large for preview (max {_MAX_PROCESSED_FILE_BYTES} bytes)",
        )
    body = target.read_bytes()
    media = mimetypes.guess_type(str(target))[0] or default_media
    return body, media


@router.get("/files")
async def list_files(
    quick: bool = Query(
        False,
        description="If true, only scan input/ (skip processed tree, documents.json, Qdrant). "
        "Use after upload to refresh the input list quickly.",
    ),
    user_id: str = Depends(storage_user_id),
) -> Dict[str, List[Dict]]:
    ensure_data_dirs(user_id)
    files: Dict[str, List[Dict]] = {"input": [], "processed": [], "indexed": []}

    storage = get_file_storage(user_id)
    files["input"] = storage.list_input_files()

    if quick:
        return files

    files["processed"] = storage.list_processed_files(include_preview=True)

    docs_path = workspace_paths_for_user(user_id).documents_json_path
    if docs_path.exists():
        try:
            with open(docs_path, "r", encoding="utf-8") as f:
                docs = json.load(f)
            sources: Dict[str, int] = {}
            for doc in docs:
                s = doc.get("source", "unknown")
                sources[s] = sources.get(s, 0) + 1
            for source, count in sources.items():
                files["indexed"].append({"name": source, "chunks": count, "type": "text"})
        except Exception as e:
            logger.error("documents.json: %s", e)

    cfg = merged_runtime_settings()
    try:
        from app.repositories import ImageIndexRepository, build_qdrant_client

        client = build_qdrant_client(cfg)
        q = cfg.get("qdrant", {}) or {}
        _, img_col = qdrant_collection_names_for_user(
            q.get("text_collection", "edu_text_chunks"),
            q.get("image_collection", "edu_image_pages"),
            workspace_paths_for_user(user_id).user_id,
        )
        ir = ImageIndexRepository(
            client,
            collection_name=img_col,
            vector_name=q.get("image_vector_name", "colpali_multivec"),
            storage_quantization=q.get("image_storage_quantization", "scalar"),
        )
        n = ir.count_points()
        if n > 0:
            files["indexed"].append(
                {"name": "Image Index (ColQwen → Qdrant)", "pages": n, "type": "image"}
            )
    except Exception:
        pass

    return files


@router.get("/processed-documents")
async def processed_documents(
    preview: bool = Query(
        False,
        description="If true, include short text previews for .md/.json/.txt artifacts (slower on large trees).",
    ),
    user_id: str = Depends(storage_user_id),
) -> Dict:
    """Structured processing tree: document folders, stages, root JSON — one call for the Processed Files UI."""
    ensure_data_dirs(user_id)
    return build_processed_documents_snapshot(user_id, include_preview=preview)


@router.get("/processed-file")
async def get_processed_file(
    rel_path: str = Query(
        ...,
        min_length=1,
        max_length=2048,
        description="Path relative to processing/ using forward slashes (e.g. stage4_rag_ready/MyDoc/file.md)",
    ),
    user_id: str = Depends(storage_user_id),
):
    """
    Download or inline-preview a single file under the user's processing tree (local or S3).
    Tenant-safe: rejects path traversal; S3 keys must stay under the configured processing prefix.
    """
    ensure_data_dirs(user_id)
    rel_posix = _sanitize_processing_rel_path(rel_path)
    body, media_type = _read_processing_file_bytes(user_id, rel_posix)
    filename = Path(rel_posix).name or "file"
    cd = f"inline; filename*=UTF-8''{urllib.parse.quote(filename)}"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": cd,
            "Cache-Control": "private, max-age=120",
        },
    )


@router.post("/upload")
async def upload(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(storage_user_id),
):
    ensure_data_dirs(user_id)
    uploaded = []
    file_rows: List[Dict] = []
    storage = get_file_storage(user_id)
    for file in files:
        try:
            content = await file.read()
            row = storage.save_upload(file.filename or "unnamed", content)
            uploaded.append({"name": row["name"], "size": len(content)})
            file_rows.append(row)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    return {"uploaded": uploaded, "count": len(uploaded), "files": file_rows}


@router.delete("/files")
async def delete_file(
    body: FileDeleteRequest,
    user_id: str = Depends(storage_user_id),
):
    storage = get_file_storage(user_id)
    try:
        if storage.delete(body.path):
            return {"deleted": body.path}
        raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
