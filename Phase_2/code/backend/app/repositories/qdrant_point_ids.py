"""Map logical string IDs to Qdrant-compatible point IDs.

Qdrant Cloud (and current Qdrant API) accept only unsigned integer or UUID point IDs.
Logical identifiers stay in payloads (chunk_id, point_id, etc.).
"""

from __future__ import annotations

import uuid

# Project-specific namespace for UUID v5 (deterministic upserts).
_PHASE2_QDRANT_POINT_NS = uuid.UUID("4e8b9c1a-2f7d-4e3b-9c6a-1d2e3f4a5b6c")


def logical_id_to_qdrant_point_id(logical_id: str) -> str:
    """Return a UUID string derived from ``logical_id`` (stable across runs)."""
    return str(uuid.uuid5(_PHASE2_QDRANT_POINT_NS, str(logical_id)))
