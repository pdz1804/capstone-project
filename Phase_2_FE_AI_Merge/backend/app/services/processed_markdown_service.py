"""Concatenate Docling / pipeline markdown under processing/ for LLM context (no vector search)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from app.core.paths import sanitize_storage_user_id, workspace_paths_for_user
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)

STAGE3 = "stage3_document_processed"
STAGE4 = "stage4_rag_ready"
_MAX_SINGLE_FILE_CHARS = 200_000
_MAX_SINGLE_FILE_BYTES = min(_MAX_SINGLE_FILE_CHARS * 4, 800_000)


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
    total = 0
    for rel, body in blocks:
        header = f"---\nFile: {rel}\n\n"
        text = (body or "").strip()
        if not text:
            continue
        block = header + text
        if total + len(block) > max_chars:
            room = max_chars - total - len(header)
            if room < 400:
                break
            block = header + text[:room] + "\n\n[truncated]"
            parts.append(block)
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def _gather_local(
    processing_root: Path,
    document_id: str | None,
    stage: str,
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
        if len(raw) > _MAX_SINGLE_FILE_CHARS:
            raw = raw[:_MAX_SINGLE_FILE_CHARS] + "\n\n[truncated file]"
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
        if sz <= _MAX_SINGLE_FILE_BYTES:
            body, _ = storage.read_object(storage.processed_bucket, key)
        else:
            rng = f"bytes=0-{_MAX_SINGLE_FILE_BYTES - 1}"
            obj = storage._client.get_object(
                Bucket=storage.processed_bucket,
                Key=key,
                Range=rng,
            )
            body = obj["Body"].read()
    except Exception as e:
        logger.debug("get_object %s: %s", key, e)
        return None
    text = body.decode("utf-8", errors="ignore")
    if len(text) > _MAX_SINGLE_FILE_CHARS or sz > _MAX_SINGLE_FILE_BYTES:
        text = text[:_MAX_SINGLE_FILE_CHARS] + "\n\n[truncated file]"
    return text


def _gather_s3(
    storage: S3FileStorage,
    document_id: str | None,
    stage: str,
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
        out.append((rel, text))
    return out


def _gather_stage(
    user_id: str | None,
    document_id: str | None,
    stage: str,
) -> List[Tuple[str, str]]:
    uid = sanitize_storage_user_id(user_id)
    paths = workspace_paths_for_user(uid)
    storage = get_file_storage(user_id)
    if isinstance(storage, S3FileStorage):
        return _gather_s3(storage, document_id, stage)
    return _gather_local(paths.processing_dir, document_id, stage)


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
