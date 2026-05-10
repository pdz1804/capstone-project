"""Status and file listing   tolerates missing Qdrant."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_status_ok(client: TestClient):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "ready" in data
    assert "indexed_docs" in data
    assert "text_index" in data
    assert "image_index" in data


@pytest.mark.unit
def test_files_list_shape(client: TestClient):
    r = client.get("/api/files")
    assert r.status_code == 200
    data = r.json()
    assert "input" in data and "processed" in data and "indexed" in data
    assert isinstance(data["input"], list)


@pytest.mark.unit
def test_files_quick_param(client: TestClient):
    r = client.get("/api/files", params={"quick": 1})
    assert r.status_code == 200
    data = r.json()
    assert "input" in data and isinstance(data["input"], list)
    assert data["processed"] == [] and data["indexed"] == []
