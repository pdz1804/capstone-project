"""Build a structured view of the processing tree (local or S3) for one storage user."""

from __future__ import annotations

import logging
import os
import time
from datetime import timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Set

from app.core.paths import workspace_paths_for_user
from app.storage import get_file_storage
from app.storage.service import S3FileStorage, _human_size, _iso_from_ts

logger = logging.getLogger(__name__)

STAGE_ORDER = (
    "stage1_normalized",
    "stage2_media_processed",
    "stage3_document_processed",
    "stage4_rag_ready",
)
STAGE_SET = frozenset(STAGE_ORDER)

_DOC_ROOT_SENTINEL = "__root__"
_SHARED_SENTINEL = "__pipeline_shared__"

_SNAPSHOT_CACHE_TTL_SECONDS = max(
    0.0,
    float(os.getenv("PROCESSED_SNAPSHOT_CACHE_TTL_SECONDS", "8") or "8"),
)
_SNAPSHOT_CACHE: Dict[tuple[str, bool, str], tuple[float, Dict[str, Any]]] = {}
_SNAPSHOT_CACHE_LOCK = Lock()


def invalidate_processed_documents_snapshot_cache(user_id: str | None = None) -> None:
    with _SNAPSHOT_CACHE_LOCK:
        if user_id is None:
            _SNAPSHOT_CACHE.clear()
            return
        target = str(user_id or "").strip()
        for key in list(_SNAPSHOT_CACHE.keys()):
            if key[0] == target:
                _SNAPSHOT_CACHE.pop(key, None)


def _snapshot_scope(user_id: str, paths: Any, storage: Any) -> str:
    uid = str(user_id or "").strip()
    if isinstance(storage, S3FileStorage):
        bucket = str(getattr(storage, "processed_bucket", "") or "")
        prefix = str(getattr(storage, "processing_prefix", "") or "")
        backend = str(getattr(storage, "backend_name", "") or "s3")
        return f"{uid}|{backend}|{bucket}|{prefix}"
    proc_dir = getattr(paths, "processing_dir", "")
    try:
        proc_key = str(Path(proc_dir).resolve()).lower()
    except Exception:
        proc_key = str(proc_dir)
    backend = str(getattr(storage, "backend_name", "") or "local")
    return f"{uid}|{backend}|{proc_key}"


def _get_cached_snapshot(user_id: str, include_preview: bool, scope: str) -> Dict[str, Any] | None:
    if _SNAPSHOT_CACHE_TTL_SECONDS <= 0:
        return None
    key = (str(user_id or "").strip(), bool(include_preview), str(scope or ""))
    with _SNAPSHOT_CACHE_LOCK:
        row = _SNAPSHOT_CACHE.get(key)
        if not row:
            return None
        cached_at, payload = row
        if (time.time() - cached_at) > _SNAPSHOT_CACHE_TTL_SECONDS:
            _SNAPSHOT_CACHE.pop(key, None)
            return None
        return payload


def _store_cached_snapshot(user_id: str, include_preview: bool, scope: str, payload: Dict[str, Any]) -> None:
    if _SNAPSHOT_CACHE_TTL_SECONDS <= 0:
        return
    key = (str(user_id or "").strip(), bool(include_preview), str(scope or ""))
    with _SNAPSHOT_CACHE_LOCK:
        _SNAPSHOT_CACHE[key] = (time.time(), payload)


def _file_row(
    *,
    rel: str,
    path: str,
    name: str,
    size_bytes: int,
    modified_iso: str,
    storage: str,
    preview: str | None = None,
) -> Dict[str, Any]:
    suf = Path(name).suffix.lower()
    row: Dict[str, Any] = {
        "name": name,
        "relative_path": rel,
        "path": path,
        "size": _human_size(size_bytes),
        "size_bytes": size_bytes,
        "modified": modified_iso,
        "type": suf,
        "storage": storage,
    }
    if preview is not None:
        row["preview"] = preview
    return row


def _preview_local(path: Path, max_bytes: int | None = None) -> str | None:
    suf = path.suffix.lower()
    if suf not in {".json", ".md", ".txt"}:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            return fp.read() if max_bytes is None else fp.read(max_bytes)
    except OSError:
        return None


def _preview_s3(client: Any, bucket: str, key: str, total_size: int) -> str | None:
    suf = Path(key).suffix.lower()
    if suf not in {".json", ".md", ".txt"}:
        return None
    try:
        prev = client.get_object(Bucket=bucket, Key=key)
        body = prev["Body"].read()
        return body.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug("S3 preview skip %s: %s", key, e)
        return None


def _collect_local(processing_dir: Path, include_preview: bool, storage_name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not processing_dir.exists():
        return rows
    for f in processing_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            rel = f.relative_to(processing_dir).as_posix()
        except ValueError:
            continue
        stat = f.stat()
        preview = _preview_local(f) if include_preview else None
        rows.append(
            _file_row(
                rel=rel,
                path=str(f.resolve()),
                name=f.name,
                size_bytes=stat.st_size,
                modified_iso=_iso_from_ts(stat.st_mtime),
                storage=storage_name,
                preview=preview,
            )
        )
    return rows


def _collect_s3(storage: S3FileStorage, include_preview: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    paginator = storage._client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=storage.processed_bucket, Prefix=storage.processing_prefix):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            if key.endswith("/"):
                continue
            rel = key[len(storage.processing_prefix) :] if storage.processing_prefix else key
            rel = rel.lstrip("/")
            if not rel or ".." in rel.split("/"):
                continue
            lm = obj["LastModified"]
            if lm.tzinfo is None:
                lm = lm.replace(tzinfo=timezone.utc)
            sz = int(obj["Size"])
            preview = None
            if include_preview:
                preview = _preview_s3(storage._client, storage.processed_bucket, key, sz)
            rows.append(
                _file_row(
                    rel=rel,
                    path=storage._uri(storage.processed_bucket, key),
                    name=Path(key).name,
                    size_bytes=sz,
                    modified_iso=lm.isoformat(),
                    storage=storage.backend_name,
                    preview=preview,
                )
            )
    return rows


def _discover_doc_ids(entries: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for e in entries:
        parts = e["relative_path"].split("/")
        if len(parts) >= 3 and parts[0] == "stage4_rag_ready":
            ids.add(parts[1])
        if len(parts) >= 3 and parts[0] == "stage3_document_processed":
            ids.add(parts[1])
    return ids


def _assign_document(rel: str, doc_ids: Set[str]) -> str:
    parts = rel.split("/")
    if not parts or parts == [""]:
        return _DOC_ROOT_SENTINEL
    head = parts[0]
    if head not in STAGE_SET:
        return _DOC_ROOT_SENTINEL
    if head in ("stage4_rag_ready", "stage3_document_processed") and len(parts) >= 3:
        return parts[1]
    # stage1 / stage2: match document folder name as a path segment (longest first)
    for d in sorted(doc_ids, key=len, reverse=True):
        if d in parts:
            return d
    stem = Path(parts[-1]).stem
    if stem in doc_ids:
        return stem
    for d in doc_ids:
        if d in parts[-1] or parts[-1].startswith(d):
            return d
    return _SHARED_SENTINEL


def _stage_for_rel(rel: str) -> str | None:
    parts = rel.split("/")
    if not parts:
        return None
    if parts[0] in STAGE_SET:
        return parts[0]
    return None


def build_processed_documents_snapshot(user_id: str, *, include_preview: bool = False) -> Dict[str, Any]:
    """
    Single-call layout for UI: input file count, per-document stage folders, root JSON, shared artifacts.
    """
    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)
    scope = _snapshot_scope(user_id, paths, storage)

    cached = _get_cached_snapshot(user_id, include_preview, scope)
    if cached is not None:
        return cached

    if isinstance(storage, S3FileStorage):
        entries = _collect_s3(storage, include_preview)
    else:
        entries = _collect_local(paths.processing_dir, include_preview, storage.backend_name)

    input_rows = storage.list_input_files()
    doc_ids = _discover_doc_ids(entries)
    if not doc_ids and entries:
        # No stage3/4 folders yet   one synthetic "workspace" bucket for flat outputs
        doc_ids = set()

    root_files: List[Dict[str, Any]] = []
    shared_files: List[Dict[str, Any]] = []
    per_doc: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def ensure_doc(did: str) -> Dict[str, List[Dict[str, Any]]]:
        if did not in per_doc:
            per_doc[did] = {s: [] for s in STAGE_ORDER}
        return per_doc[did]

    for e in entries:
        rel = e["relative_path"]
        bucket = _assign_document(rel, doc_ids)
        st = _stage_for_rel(rel)
        row = dict(e)

        if bucket == _DOC_ROOT_SENTINEL:
            root_files.append(row)
            continue
        if bucket == _SHARED_SENTINEL:
            if st:
                shared_files.append(row)
            else:
                root_files.append(row)
            continue
        dmap = ensure_doc(bucket)
        if st:
            dmap[st].append(row)
        else:
            root_files.append(row)

    # Real documents only (exclude sentinels from count)
    doc_list: List[Dict[str, Any]] = []
    for did in sorted(per_doc.keys(), key=str.lower):
        st_map = per_doc[did]
        total = sum(len(v) for v in st_map.values())
        doc_list.append(
            {
                "id": did,
                "display_name": did,
                "total_files": total,
                "stages": {s: {"file_count": len(st_map[s]), "files": st_map[s]} for s in STAGE_ORDER},
            }
        )

    shared_payload: Dict[str, Any] | None = None
    if shared_files:
        by_stage: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STAGE_ORDER}
        for row in shared_files:
            st = _stage_for_rel(row["relative_path"])
            if st:
                by_stage[st].append(row)
        shared_payload = {
            "id": _SHARED_SENTINEL,
            "display_name": "Pipeline-wide · metadata & stats",
            "total_files": len(shared_files),
            "stages": {s: {"file_count": len(by_stage[s]), "files": by_stage[s]} for s in STAGE_ORDER},
        }

    out_docs = doc_list
    if shared_payload and shared_payload["total_files"] > 0:
        out_docs = doc_list + [shared_payload]

    artifact_count = len(entries)
    stage_totals: Dict[str, int] = {s: 0 for s in STAGE_ORDER}
    for e in entries:
        st = _stage_for_rel(e["relative_path"])
        if st:
            stage_totals[st] = stage_totals.get(st, 0) + 1

    # Sidebar rows = per-source folders under stage3/4 plus optional shared bucket (must match len(documents)).
    document_group_count = len(out_docs)
    # Folders discovered only from stage3/stage4 paths (excludes shared/metadata-only bucket).
    named_document_folders = len(doc_list)

    payload = {
        "input_file_count": len(input_rows),
        "artifact_count": artifact_count,
        "document_count": document_group_count,
        "named_document_folders": named_document_folders,
        "stage_order": list(STAGE_ORDER),
        "stage_totals": stage_totals,
        "root_file_count": len(root_files),
        "root_files": sorted(root_files, key=lambda r: r["relative_path"].lower()),
        "documents": out_docs,
        # Short hints for the UI (stage totals > input count is normal: copies, chunks, JSON metadata).
        "count_hints": {
            "stage_totals": (
                "Stage totals = every file in that stage folder (PDF copies, chunk .md files, stats JSON, …). "
                "They are usually much larger than “input files” because the pipeline duplicates and splits content."
            ),
            "document_groups": (
                "Sidebar rows = one group per document folder under stage3/stage4, plus “Pipeline-wide” for "
                "normalization/consolidation JSON and other outputs not under a single document path."
            ),
        },
    }
    _store_cached_snapshot(user_id, include_preview, scope, payload)
    return payload
