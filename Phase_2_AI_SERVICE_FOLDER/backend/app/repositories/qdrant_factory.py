"""Construct Qdrant client from merged YAML + environment (docker or cloud)."""

from __future__ import annotations

from typing import Any, Dict

from qdrant_client import QdrantClient


def build_qdrant_client(cfg: Dict[str, Any]) -> QdrantClient:
    q = cfg.get("qdrant", {}) or {}
    mode = (q.get("mode") or "docker").strip().lower()
    if mode == "cloud":
        url = (q.get("url") or "").strip()
        key = (q.get("api_key") or "").strip()
        if not url:
            raise ValueError("qdrant.mode=cloud requires qdrant.url (or QDRANT_URL).")
        return QdrantClient(url=url, api_key=key or None, timeout=120)
    host = (q.get("host") or "localhost").strip()
    port = int(q.get("port") or 6333)
    return QdrantClient(host=host, port=port, timeout=120)
