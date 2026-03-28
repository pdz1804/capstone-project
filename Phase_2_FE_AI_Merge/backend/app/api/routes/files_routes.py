import json
import logging
import mimetypes
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
from app.services.file_metadata_service import FileMetadataService
from app.storage import get_file_storage
from app.storage.service import S3FileStorage, parse_s3_uri

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["files"])

_MAX_PROCESSED_FILE_BYTES = int(os.getenv("MAX_PROCESSED_FILE_PREVIEW_BYTES", str(50 * 1024 * 1024)))


def _file_stem(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return ""
    return Path(n).stem.lower()


def _normalizer_safe_stem(name: str, max_length: int = 50) -> str:
    """Mirror Stage1 normalizer naming for long filenames (truncate + md5 suffix)."""
    stem = Path((name or "").strip()).stem.strip().rstrip(".")
    if not stem:
        stem = "untitled"
    if len(stem) <= max_length:
        return stem.lower()
    import hashlib

    hash_suffix = hashlib.md5(stem.encode("utf-8", errors="ignore")).hexdigest()[:8]
    truncated = stem[: max_length - 9]
    return f"{truncated}_{hash_suffix}".lower()


def _is_visual_artifact(name: str) -> bool:
    n = (name or "").lower()
    return n.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"))


def _match_indexed_text_source(file_name: str, source_name: str) -> bool:
    fn = file_name.lower()
    stem = _file_stem(file_name)
    src = (source_name or "").replace("\\", "/").lower()
    if not src:
        return False
    if fn in src or src.endswith("/" + fn):
        return True
    return bool(stem and stem in src)


def _find_document_entry_for_input_name(processed_snapshot: Dict[str, Any], file_name: str) -> Dict[str, Any] | None:
    docs = processed_snapshot.get("documents") or []
    target_stem = _file_stem(file_name)
    target_name = (file_name or "").lower()
    target_safe = _normalizer_safe_stem(file_name)
    if not target_stem and not target_name:
        return None
    # Prefer exact (display/id) then fallback to substring.
    for doc in docs:
        did = str(doc.get("id") or "").lower()
        dname = str(doc.get("display_name") or "").lower()
        if did == target_stem or dname == target_stem or dname == target_name or did == target_safe or dname == target_safe:
            return doc
    for doc in docs:
        did = str(doc.get("id") or "").lower()
        dname = str(doc.get("display_name") or "").lower()
        if target_stem and (target_stem in did or target_stem in dname):
            return doc
        if target_safe and (target_safe in did or target_safe in dname):
            return doc
    return None


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


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


def _read_input_file_bytes(user_id: str, file_name: str) -> Tuple[bytes, str]:
    """Return (body, media_type) for one input/original file (local or S3)."""
    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)
    guessed, _ = mimetypes.guess_type(file_name)
    default_media = guessed or "application/octet-stream"

    if isinstance(storage, S3FileStorage):
        rows = storage.list_input_files()
        match = next((r for r in rows if str(r.get("name") or "") == file_name), None)
        if not match:
            raise HTTPException(status_code=404, detail="File not found")
        uri = str(match.get("path") or "")
        parsed = storage.parse_s3_uri(uri) if hasattr(storage, "parse_s3_uri") else None
        if parsed is None:
            # fallback to module helper
            from app.storage.service import parse_s3_uri as _parse_s3_uri

            parsed = _parse_s3_uri(uri)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid input file URI")
        bucket, key = parsed
        if not storage.can_read_object(bucket, key):
            raise HTTPException(status_code=403, detail="Object not in your input prefix")
        try:
            head = storage._client.head_object(Bucket=bucket, Key=key)
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
            body, ct = storage.read_object(bucket, key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise HTTPException(status_code=404, detail="File not found") from e
            raise HTTPException(status_code=500, detail=str(e)) from e
        media = (ct or "").split(";")[0].strip() or default_media
        return body, media

    # local input
    root = paths.input_dir.resolve()
    target = (root / file_name).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside input directory") from None
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


@router.get("/files-with-metadata")
async def list_files_with_metadata(user_id: str = Depends(storage_user_id)) -> Dict[str, Any]:
    """
    Return uploaded input files enriched with lightweight metadata/status.

    Works for local + S3 by combining:
    - /files input/indexed view
    - processed-documents snapshot (stage-level artifacts)
    - optional local companion metadata json (if available)
    """
    ensure_data_dirs(user_id)
    storage = get_file_storage(user_id)
    input_rows = storage.list_input_files()
    processed_snapshot = build_processed_documents_snapshot(user_id, include_preview=False)
    docs = processed_snapshot.get("documents") or []
    stage_totals = processed_snapshot.get("stage_totals") or {}
    indexed_rows: List[Dict[str, Any]] = []
    try:
        indexed_rows = (await list_files(quick=False, user_id=user_id)).get("indexed") or []
    except Exception:
        indexed_rows = []

    text_sources = [
        str(r.get("name") or "")
        for r in indexed_rows
        if str(r.get("type") or "").lower() != "image"
    ]
    image_index_exists = any(str(r.get("type") or "").lower() == "image" for r in indexed_rows)

    metadata_svc = FileMetadataService()
    out: List[Dict[str, Any]] = []
    for row in input_rows:
        name = str(row.get("name") or "")
        input_path = str(row.get("path") or "")
        doc_entry = _find_document_entry_for_input_name(processed_snapshot, name)
        doc_stages = (doc_entry or {}).get("stages") or {}
        doc_total_files = int((doc_entry or {}).get("total_files") or 0)
        stage4_files = ((doc_stages.get("stage4_rag_ready") or {}).get("files") or [])
        has_stage4_visuals = any(_is_visual_artifact(str((f or {}).get("name") or "")) for f in stage4_files)

        indexed_text = any(_match_indexed_text_source(name, src) for src in text_sources)
        indexed_image = image_index_exists and has_stage4_visuals
        index_status = "none"
        if indexed_text and indexed_image:
            index_status = "all"
        elif indexed_text:
            index_status = "text"
        elif indexed_image:
            index_status = "image"
        status = "uploaded"
        if indexed_text or indexed_image:
            status = "indexed"
        elif doc_total_files > 0:
            status = "processed"

        local_meta = None
        try:
            if input_path and not input_path.startswith("s3://"):
                local_meta = metadata_svc.load_metadata(input_path)
        except Exception:
            local_meta = None

        out.append(
            {
                **row,
                "file_name": name,
                "document_id": (doc_entry or {}).get("id") or _file_stem(name),
                "processed_display_name": (doc_entry or {}).get("display_name"),
                "processed_safe_name": _normalizer_safe_stem(name),
                "indexed_text": indexed_text,
                "indexed_image": indexed_image,
                "index_status": index_status,
                "status": status,
                "upload_time": (local_meta.upload_time if local_meta else None) or row.get("modified"),
                "metadata_status": (local_meta.status if local_meta else None),
                "metadata_error": (local_meta.error_message if local_meta else None),
                "processed_total_files": doc_total_files,
                "processed_stage_counts": {
                    s: int((doc_stages.get(s) or {}).get("file_count") or 0)
                    for s in ("stage1_normalized", "stage2_media_processed", "stage3_document_processed", "stage4_rag_ready")
                },
            }
        )

    return {
        "count": len(out),
        "files": out,
        "pipeline_stage_totals": stage_totals,
        "pipeline_document_count": int(processed_snapshot.get("document_count") or len(docs)),
    }


@router.get("/files/{file_name}/processed")
async def get_file_processed_artifacts(file_name: str, user_id: str = Depends(storage_user_id)) -> Dict[str, Any]:
    """
    Return processed artifacts grouped by pipeline stage for one selected uploaded file.
    """
    ensure_data_dirs(user_id)
    if not file_name:
        raise HTTPException(status_code=400, detail="file_name is required")

    decoded_name = urllib.parse.unquote(file_name).strip()
    processed_snapshot = build_processed_documents_snapshot(user_id, include_preview=True)
    doc_entry = _find_document_entry_for_input_name(processed_snapshot, decoded_name)
    if not doc_entry:
        raise HTTPException(status_code=404, detail=f"No processed artifacts found for file '{decoded_name}'")

    stages = []
    total = 0
    for stage_key in ("stage1_normalized", "stage2_media_processed", "stage3_document_processed", "stage4_rag_ready"):
        stage_data = (doc_entry.get("stages") or {}).get(stage_key) or {}
        files = stage_data.get("files") or []
        count = int(stage_data.get("file_count") or len(files))
        total += count
        stages.append({"stage": stage_key, "file_count": count, "files": files})

    return {
        "file_name": decoded_name,
        "document_id": doc_entry.get("id"),
        "display_name": doc_entry.get("display_name"),
        "total_processed_files": total,
        "stages": stages,
    }


@router.get("/files/{file_name}/chunks")
async def get_file_all_chunks(file_name: str, user_id: str = Depends(storage_user_id)) -> Dict[str, Any]:
    """
    Return ALL transcript/media chunks for one selected file, ordered by timestamp range.
    No semantic search is used here.
    """
    ensure_data_dirs(user_id)
    decoded_name = urllib.parse.unquote(file_name).strip()
    if not decoded_name:
        raise HTTPException(status_code=400, detail="file_name is required")

    processed_snapshot = build_processed_documents_snapshot(user_id, include_preview=False)
    doc_entry = _find_document_entry_for_input_name(processed_snapshot, decoded_name)
    if not doc_entry:
        raise HTTPException(status_code=404, detail=f"No processed artifacts found for file '{decoded_name}'")

    stage4 = ((doc_entry.get("stages") or {}).get("stage4_rag_ready") or {}).get("files") or []
    # Prefer transcript_chunks.json; fallback to any .json in stage4 that has {"chunks":[...]}.
    candidates: List[str] = []
    for row in stage4:
        rel = str((row or {}).get("relative_path") or "")
        if not rel:
            continue
        if rel.endswith("/transcript_chunks.json") or rel.endswith("transcript_chunks.json"):
            candidates.insert(0, rel)
        elif rel.lower().endswith(".json"):
            candidates.append(rel)

    if not candidates:
        return {
            "file_name": decoded_name,
            "document_id": doc_entry.get("id"),
            "chunk_count": 0,
            "chunks": [],
        }

    chunks: List[Dict[str, Any]] = []
    loaded_from = None
    for rel_path in candidates:
        try:
            body, _ = _read_processing_file_bytes(user_id, rel_path)
            payload = json.loads(body.decode("utf-8", errors="ignore"))
            arr = payload.get("chunks") if isinstance(payload, dict) else None
            if isinstance(arr, list) and arr:
                for i, c in enumerate(arr):
                    if not isinstance(c, dict):
                        continue
                    chunks.append(
                        {
                            "id": c.get("chunk_name") or c.get("id") or f"chunk_{i}",
                            "text": c.get("text", ""),
                            "start_time": _as_float(c.get("start_time"), default=0.0),
                            "end_time": _as_float(c.get("end_time"), default=0.0),
                            "duration": _as_float(c.get("duration"), default=0.0),
                            "source": rel_path,
                            "content_type": c.get("content_type") or "transcript_text",
                            "original_file": c.get("original_file") or decoded_name,
                        }
                    )
                loaded_from = rel_path
                break
        except Exception:
            continue

    chunks.sort(key=lambda x: (x.get("start_time", 0.0), x.get("end_time", 0.0), str(x.get("id") or "")))
    return {
        "file_name": decoded_name,
        "document_id": doc_entry.get("id"),
        "loaded_from": loaded_from,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


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


@router.get("/input-file")
async def get_input_file(
    file_name: str = Query(
        ...,
        min_length=1,
        max_length=1024,
        description="Exact input file name to preview/download.",
    ),
    user_id: str = Depends(storage_user_id),
):
    """
    Download or inline-preview a single uploaded original file from input storage (local or S3).
    """
    ensure_data_dirs(user_id)
    safe_name = Path(file_name).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid file_name")
    body, media_type = _read_input_file_bytes(user_id, safe_name)
    cd = f"inline; filename*=UTF-8''{urllib.parse.quote(safe_name)}"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": cd,
            "Cache-Control": "private, max-age=120",
        },
    )


@router.get("/input-file-url")
async def get_input_file_url(
    file_name: str = Query(
        ...,
        min_length=1,
        max_length=1024,
        description="Exact input file name to generate a temporary public URL (S3 backend only).",
    ),
    expires_in: int = Query(900, ge=60, le=3600, description="URL TTL in seconds."),
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    """
    Return a temporary presigned URL for one input/original file.
    Useful for Office web viewers that cannot send app auth headers.
    """
    ensure_data_dirs(user_id)
    safe_name = Path(file_name).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid file_name")

    storage = get_file_storage(user_id)
    if not isinstance(storage, S3FileStorage):
        return {"url": None, "mode": "not_available", "reason": "Presigned URL is available only for S3 storage."}

    rows = storage.list_input_files()
    row = next((r for r in rows if str(r.get("name") or "") == safe_name), None)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    uri = str(row.get("path") or "")
    parsed = parse_s3_uri(uri)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid input file URI")
    bucket, key = parsed
    if not storage.can_read_object(bucket, key):
        raise HTTPException(status_code=403, detail="Object not in your input prefix")

    try:
        cd = f"inline; filename*=UTF-8''{urllib.parse.quote(safe_name)}"
        guessed_type = mimetypes.guess_type(safe_name)[0]
        params: Dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "ResponseContentDisposition": cd,
        }
        # Force browser-inline rendering for known previewable files (especially PDFs).
        if guessed_type:
            params["ResponseContentType"] = guessed_type
        url = storage._client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return {"url": url, "mode": "presigned_s3", "expires_in": expires_in}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate presigned URL: {e}") from e


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
            row = storage.save_upload(file.filename or "unnamed", content, user_id=user_id)
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


@router.get("/file-metadata/{file_name}")
async def get_file_metadata(
    file_name: str,
    user_id: str = Depends(storage_user_id),
):
    """Get metadata for a specific file."""
    ensure_data_dirs(user_id)
    paths = workspace_paths_for_user(user_id)
    
    decoded_name = urllib.parse.unquote(file_name).strip()
    storage = get_file_storage(user_id)
    input_rows = storage.list_input_files()
    row = next((r for r in input_rows if str(r.get("name") or "") == decoded_name), None)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    metadata_obj: Dict[str, Any] | None = None
    row_path = str(row.get("path") or "")
    metadata_svc = FileMetadataService()
    try:
        if row_path.startswith("s3://") and isinstance(storage, S3FileStorage):
            parsed = parse_s3_uri(row_path)
            if parsed:
                bucket, key = parsed
                meta_obj = storage._client.get_object(Bucket=bucket, Key=f"{key}.metadata.json")
                body = meta_obj["Body"].read().decode("utf-8", errors="ignore")
                metadata_obj = json.loads(body) if body else None
        elif row_path:
            metadata = metadata_svc.load_metadata(Path(row_path))
            if metadata:
                metadata_obj = metadata.to_dict()
    except Exception:
        metadata_obj = None

    processed_snapshot = build_processed_documents_snapshot(user_id, include_preview=False)
    doc_entry = _find_document_entry_for_input_name(processed_snapshot, decoded_name)

    return {
        "file_name": decoded_name,
        "file_path": row_path,
        "storage": row.get("storage"),
        "processed_document_id": (doc_entry or {}).get("id"),
        "processed_display_name": (doc_entry or {}).get("display_name"),
        "processed_safe_name": _normalizer_safe_stem(decoded_name),
        "metadata": metadata_obj,
    }


@router.get("/files-metadata-stats")
async def get_files_metadata_stats(
    user_id: str = Depends(storage_user_id),
) -> Dict:
    """Get aggregate metadata statistics for all files in user's workspace."""
    ensure_data_dirs(user_id)
    paths = workspace_paths_for_user(user_id)
    
    metadata_svc = FileMetadataService()
    stats = metadata_svc.get_processing_stats(paths.input_dir)
    
    return {
        "workspace_stats": stats,
        "input_directory": str(paths.input_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/files-by-status")
async def get_files_by_status(
    status: str = Query("pending", description="Filter by processing status: pending, processing, completed, or failed"),
    user_id: str = Depends(storage_user_id),
) -> Dict:
    """List all files grouped by processing status."""
    ensure_data_dirs(user_id)
    paths = workspace_paths_for_user(user_id)
    
    if status not in ("pending", "processing", "completed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status filter")
    
    metadata_svc = FileMetadataService()
    all_files = metadata_svc.list_file_metadata(paths.input_dir, status_filter=status)
    
    files_list = [
        {
            "name": m.original_filename,
            "path": m.file_path,
            "size": m.file_size,
            "upload_time": m.upload_time,
            "status": m.status,
            "completed_stages": m.completed_stages,
            "error": m.error_message,
        }
        for m in all_files
    ]
    
    return {
        "status_filter": status,
        "count": len(files_list),
        "files": files_list,
    }
