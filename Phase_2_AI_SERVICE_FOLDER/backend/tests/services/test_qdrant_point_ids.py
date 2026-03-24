"""Qdrant point id mapping."""

from __future__ import annotations

import uuid

import pytest

from app.repositories.qdrant_point_ids import logical_id_to_qdrant_point_id


@pytest.mark.unit
def test_logical_to_uuid_deterministic():
    a = logical_id_to_qdrant_point_id("doc_chunk_0")
    b = logical_id_to_qdrant_point_id("doc_chunk_0")
    assert a == b
    uuid.UUID(a)  # valid UUID string


@pytest.mark.unit
def test_logical_to_uuid_distinct():
    assert logical_id_to_qdrant_point_id("a") != logical_id_to_qdrant_point_id("b")
