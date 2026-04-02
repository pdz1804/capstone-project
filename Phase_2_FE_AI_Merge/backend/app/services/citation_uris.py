"""Map local workspace paths to canonical S3 URIs for citations (FILE_STORAGE_BACKEND=s3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.storage import get_file_storage
from app.storage.service import S3FileStorage


def enrich_chunk_documents_storage_uris(
    documents: List[Dict[str, Any]],
    *,
    user_id: str | None,
) -> None:
    """
    Mutate chunk dicts in place: set ``metadata.storage_uri`` and ``metadata.storage_backend``
    when the path maps to an object under this user's S3 prefixes.
    """
    storage = get_file_storage(user_id)
    if not isinstance(storage, S3FileStorage):
        return

    for d in documents:
        meta = d.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            d["metadata"] = meta

        uri: Optional[str] = None
        src = d.get("source")
        if src:
            uri = storage.uri_for_local_under_processing(Path(str(src)))
        if not uri and meta.get("original_file"):
            of = Path(str(meta["original_file"]))
            uri = storage.uri_for_local_under_processing(of)
            if not uri:
                uri = storage.uri_for_local_under_input(of)

        if uri:
            meta["storage_uri"] = uri
            meta["storage_backend"] = "s3"


def sanitize_metadata_for_api(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Copy of chunk metadata safe for API/UI: when ``storage_uri`` is set, drop ``original_file`` so
    clients never use ephemeral local paths for loading or display.
    """
    out = dict(meta or {})
    su = str(out.get("storage_uri") or "").strip()
    if su:
        out.pop("original_file", None)
        out.pop("source_path", None)
    return out


def canonical_document_source(meta: Dict[str, Any], fallback: str) -> str:
    """Prefer S3 ``storage_uri`` over local ``source`` / path strings."""
    su = str((meta or {}).get("storage_uri") or "").strip()
    if su:
        return su
    return (fallback or "").strip()
