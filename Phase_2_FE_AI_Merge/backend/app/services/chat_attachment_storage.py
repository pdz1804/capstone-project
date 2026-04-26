"""Persist chat infographic PNGs under processing/chat_attachments (S3 or local workspace)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from app.storage import get_file_storage

logger = logging.getLogger(__name__)

_PREFIX = "chat_attachments"


def _ext_for_mime(mime: str) -> str:
    m = (mime or "").lower()
    if "png" in m:
        return ".png"
    if "webp" in m:
        return ".webp"
    if "jpeg" in m or "jpg" in m:
        return ".jpg"
    return ".bin"


def persist_chat_visualization_png(
    user_id: str,
    session_id: str,
    message_id: str,
    slot: int,
    data: bytes,
    mime: str,
) -> str:
    """Return relative path under ``processing/`` (posix) for DynamoDB."""
    rel = f"{_PREFIX}/{session_id}/{message_id}_{int(slot)}{_ext_for_mime(mime)}"
    storage = get_file_storage(user_id)
    ct = (mime or "image/png").split(";")[0].strip() or "image/png"

    if getattr(storage, "backend_name", "") == "s3":
        storage.write_processed_bytes(rel, data, content_type=ct)
        return rel

    proc_dir = getattr(storage, "processing_dir", None)
    if proc_dir is None:
        raise RuntimeError("Local storage has no processing_dir")
    dest = Path(proc_dir) / rel.replace("/", os.sep)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel


def read_chat_attachment_bytes(user_id: str, rel_path: str) -> Optional[Tuple[bytes, str]]:
    """Read bytes for a stored chat attachment; return (body, content_type) or None."""
    rel = (rel_path or "").strip().lstrip("/").replace("\\", "/")
    if not rel.startswith(f"{_PREFIX}/") or ".." in rel:
        return None

    storage = get_file_storage(user_id)
    if getattr(storage, "backend_name", "") == "s3":
        try:
            body = storage.read_processed_bytes(rel)
        except Exception as e:
            logger.warning("read chat attachment s3 %s: %s", rel, e)
            return None
        if not body:
            return None
        return body, "image/png"

    proc_dir = getattr(storage, "processing_dir", None)
    if proc_dir is None:
        return None
    dest = Path(proc_dir) / rel.replace("/", os.sep)
    try:
        if not dest.is_file():
            return None
        body = dest.read_bytes()
    except OSError as e:
        logger.warning("read chat attachment local %s: %s", rel, e)
        return None
    return body, "image/png"
