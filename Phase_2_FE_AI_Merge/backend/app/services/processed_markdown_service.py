"""Concatenate Docling / pipeline markdown under processing/ for LLM context (no vector search)."""

from __future__ import annotations

import logging
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.paths import sanitize_storage_user_id, workspace_paths_for_user
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)

STAGE3 = "stage3_document_processed"
STAGE4 = "stage4_rag_ready"


def _safe_document_folder(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s or ".." in s or "/" in s or "\\" in s:
        return None
    return s


def sanitize_insights_document_id(document_id: str | None) -> str | None:
    """Return folder name for scope, or None (all docs). If input was non-empty but unsafe, returns None."""
    raw = (document_id or "").strip()
    if not raw:
        return None
    return _safe_document_folder(document_id)


def _join_md_blocks(blocks: List[Tuple[str, str]], max_chars: int) -> str:
    parts: List[str] = []
    for rel, body in blocks:
        header = f"---\nFile: {rel}\n\n"
        text = (body or "").strip()
        if not text:
            continue
        parts.append(header + text)
    return "\n\n".join(parts)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_timestamp(seconds: Any) -> str:
    value = max(0.0, _as_float(seconds))
    whole = int(value)
    hh = whole // 3600
    mm = (whole % 3600) // 60
    ss = whole % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _markdown_has_frame_links(body: str) -> bool:
    lowered = (body or "").lower()
    return "](frames/" in lowered or "frame-aligned lecture notes" in lowered


def _frame_filename(frame: Dict[str, Any]) -> str:
    raw_path = str(frame.get("frame_path") or "").replace("\\", "/").strip()
    name = Path(raw_path).name if raw_path else ""
    if not name and frame.get("frame_index") is not None:
        name = f"frame_{int(_as_float(frame.get('frame_index'))):06d}.jpg"
    if not name:
        raw_name = str(frame.get("frame_name") or "").strip()
        name = Path(raw_name).name if raw_name else ""
    if not name:
        name = "frame_000000.jpg"
    if "." not in name:
        name = f"{name}.jpg"
    return name


def _representative_frame(chunk: Dict[str, Any]) -> Dict[str, Any] | None:
    frames = chunk.get("associated_frames")
    if not isinstance(frames, list):
        return None
    candidates = [frame for frame in frames if isinstance(frame, dict)]
    if not candidates:
        return None
    start = _as_float(chunk.get("start_time"))
    end = _as_float(chunk.get("end_time"), start)
    midpoint = start + max(0.0, end - start) / 2.0
    return min(candidates, key=lambda frame: abs(_as_float(frame.get("video_timestamp"), midpoint) - midpoint))


def _representative_frame_filenames(payload: Dict[str, Any]) -> List[str]:
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        frame = _representative_frame(chunk)
        if not frame:
            continue
        filename = _frame_filename(frame)
        if filename and filename not in seen:
            seen.add(filename)
            out.append(filename)
    return out


def _render_media_lecture_markdown(stem: str, payload: Dict[str, Any], source_name: str | None = None) -> str | None:
    chunks = payload.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return None
    rows = [chunk for chunk in chunks if isinstance(chunk, dict) and str(chunk.get("text") or "").strip()]
    if not rows or not any(isinstance(row.get("associated_frames"), list) and row.get("associated_frames") for row in rows):
        return None

    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    source = source_name or f"{stem}.mp4"
    lines = [
        f"# Lecture: {stem}",
        "",
        f"**Source:** {source}  ",
        f"**Language:** {meta.get('language') or 'unknown'}  ",
        f"**Chunks:** {len(rows)}",
        "",
    ]
    for chunk in rows:
        start = _as_float(chunk.get("start_time"))
        end = _as_float(chunk.get("end_time"), start)
        lines.extend([f"## {_format_timestamp(start)} - {_format_timestamp(end)}", ""])
        frame = _representative_frame(chunk)
        if frame:
            lines.extend(
                [
                    f"![Frame at {_format_timestamp(frame.get('video_timestamp'))}](frames/{_frame_filename(frame)})",
                    "",
                ]
            )
        lines.extend([str(chunk.get("text") or "").strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _append_unique_image_path(image_paths: List[str] | None, image_path: str, max_images: int) -> None:
    if image_paths is None or len(image_paths) >= max_images:
        return
    if image_path and image_path not in image_paths:
        image_paths.append(image_path)


def _read_s3_body_bytes(storage: S3FileStorage, key: str) -> bytes | None:
    bucket = storage.processed_bucket
    if not storage.can_read_object(bucket, key):
        return None
    try:
        body, _ = storage.read_object(bucket, key)
        return body
    except Exception as e:
        logger.debug("get_object bytes %s: %s", key, e)
        return None


def _materialize_s3_image_to_temp(storage: S3FileStorage, key: str) -> str | None:
    body = _read_s3_body_bytes(storage, key)
    if not body:
        return None
    suffix = Path(key).suffix.lower() or ".jpg"
    fd, name = tempfile.mkstemp(prefix="summary_frame_", suffix=suffix)
    try:
        os.write(fd, body)
    finally:
        os.close(fd)
    return name


def _gather_local(
    processing_root: Path,
    document_id: str | None,
    stage: str,
    image_paths: List[str] | None = None,
    max_images: int = 8,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    base = processing_root / stage
    if not base.is_dir():
        return out
    if document_id:
        doc_dir = base / document_id
        if not doc_dir.is_dir():
            return out
        md_files = sorted(doc_dir.rglob("*"))
    else:
        md_files = sorted(base.rglob("*"))
    for f in md_files:
        if not f.is_file() or f.suffix.lower() != ".md":
            continue
        try:
            rel = f.relative_to(processing_root).as_posix()
        except ValueError:
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.debug("skip md %s: %s", f, e)
            continue
        if stage == STAGE4:
            chunks_file = f.parent / "transcript_chunks.json"
            if chunks_file.exists():
                try:
                    payload = json.loads(chunks_file.read_text(encoding="utf-8", errors="ignore"))
                    if not _markdown_has_frame_links(raw):
                        rendered = _render_media_lecture_markdown(f.parent.name, payload, f"{f.parent.name}.mp4")
                    else:
                        rendered = None
                    if rendered:
                        raw = rendered
                    frames_dir = f.parent / "frames"
                    for filename in _representative_frame_filenames(payload):
                        frame_path = frames_dir / filename
                        if frame_path.exists():
                            _append_unique_image_path(image_paths, str(frame_path), max_images)
                except Exception as e:
                    logger.debug("skip media lecture markdown synthesis for %s: %s", f, e)
        out.append((rel, raw))
    return out


def _read_s3_md_body(storage: S3FileStorage, key: str) -> str | None:
    if not storage.can_read_object(storage.processed_bucket, key):
        return None
    try:
        head = storage._client.head_object(Bucket=storage.processed_bucket, Key=key)
        sz = int(head.get("ContentLength") or 0)
    except Exception as e:
        logger.debug("head_object %s: %s", key, e)
        return None
    try:
        body, _ = storage.read_object(storage.processed_bucket, key)
    except Exception as e:
        logger.debug("get_object %s: %s", key, e)
        return None
    return body.decode("utf-8", errors="ignore")


def _gather_s3(
    storage: S3FileStorage,
    document_id: str | None,
    stage: str,
    image_paths: List[str] | None = None,
    max_images: int = 8,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    prefix_base = storage.processing_prefix
    if document_id:
        sub = f"{stage}/{document_id}/"
    else:
        sub = f"{stage}/"
    full_prefix = f"{prefix_base}{sub}" if prefix_base else sub
    client = storage._client
    bucket = storage.processed_bucket
    keys: List[str] = []
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=full_prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.endswith("/") or not key.lower().endswith(".md"):
                    continue
                keys.append(key)
    except Exception as e:
        logger.warning("list_objects %s: %s", full_prefix, e)
        return out
    keys.sort()
    strip = len(prefix_base) if prefix_base else 0
    for key in keys:
        text = _read_s3_md_body(storage, key)
        if not text or not text.strip():
            continue
        rel = key[strip:].lstrip("/") if strip else key
        if stage == STAGE4:
            parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
            stem = parent.rsplit("/", 1)[-1] if parent else Path(rel).stem
            chunks_rel = f"{parent}/transcript_chunks.json" if parent else "transcript_chunks.json"
            chunks_key = f"{prefix_base}{chunks_rel}" if prefix_base else chunks_rel
            chunks_text = _read_s3_md_body(storage, chunks_key)
            if chunks_text:
                try:
                    payload = json.loads(chunks_text)
                    if not _markdown_has_frame_links(text):
                        rendered = _render_media_lecture_markdown(stem, payload, f"{stem}.mp4")
                    else:
                        rendered = None
                    if rendered:
                        text = rendered
                    for filename in _representative_frame_filenames(payload):
                        if image_paths is None or len(image_paths) >= max_images:
                            break
                        frame_rel = f"{parent}/frames/{filename}" if parent else f"frames/{filename}"
                        frame_key = f"{prefix_base}{frame_rel}" if prefix_base else frame_rel
                        temp_path = _materialize_s3_image_to_temp(storage, frame_key)
                        if temp_path:
                            _append_unique_image_path(image_paths, temp_path, max_images)
                except Exception as e:
                    logger.debug("skip media lecture markdown synthesis for %s: %s", rel, e)
        out.append((rel, text))
    return out


def _gather_stage(
    user_id: str | None,
    document_id: str | None,
    stage: str,
    image_paths: List[str] | None = None,
    max_images: int = 8,
) -> List[Tuple[str, str]]:
    uid = sanitize_storage_user_id(user_id)
    paths = workspace_paths_for_user(uid)
    storage = get_file_storage(user_id)
    if isinstance(storage, S3FileStorage):
        return _gather_s3(storage, document_id, stage, image_paths=image_paths, max_images=max_images)
    return _gather_local(paths.processing_dir, document_id, stage, image_paths=image_paths, max_images=max_images)


def gather_processed_markdown_context(
    user_id: str | None,
    document_id: str | None,
    max_chars: int,
) -> str:
    """
    Load markdown from pipeline outputs: prefer stage3 (Docling full-document MD), then stage4
    RAG-ready copies if stage3 is empty. Does not call Qdrant or embedding models.
    """
    raw = (document_id or "").strip()
    doc = _safe_document_folder(document_id)
    if raw and doc is None:
        return ""
    blocks = _gather_stage(user_id, doc, STAGE3)
    text = _join_md_blocks(blocks, max_chars)
    if text.strip():
        return text
    blocks4 = _gather_stage(user_id, doc, STAGE4)
    return _join_md_blocks(blocks4, max_chars)


def gather_processed_markdown_context_with_images(
    user_id: str | None,
    document_id: str | None,
    max_chars: int,
    max_images: int = 8,
) -> Tuple[str, List[str]]:
    """
    Load processed markdown plus representative media frame image paths.

    This mirrors gather_processed_markdown_context, but when Stage 4 media chunks include
    associated frames, it returns actual image files for multimodal LLM calls.
    """
    raw = (document_id or "").strip()
    doc = _safe_document_folder(document_id)
    if raw and doc is None:
        return "", []

    image_paths: List[str] = []
    blocks = _gather_stage(user_id, doc, STAGE3, image_paths=image_paths, max_images=max_images)
    text = _join_md_blocks(blocks, max_chars)
    if text.strip():
        return text, image_paths

    blocks4 = _gather_stage(user_id, doc, STAGE4, image_paths=image_paths, max_images=max_images)
    return _join_md_blocks(blocks4, max_chars), image_paths
