"""GET /api/processed-file — tenant-safe read under processing/."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_processed_file_rejects_traversal(client: TestClient):
    r = client.get("/api/processed-file", params={"rel_path": "../secrets"})
    assert r.status_code == 400


@pytest.mark.unit
def test_processed_file_local_happy_path(client: TestClient, tmp_path, monkeypatch):
    from app.core.paths import workspace_paths_for_user as real_wp

    proc = tmp_path / "processing"
    (proc / "stage1_normalized").mkdir(parents=True)
    (proc / "stage1_normalized" / "hello.md").write_text("# Hi", encoding="utf-8")

    def wp(uid=None):
        return replace(real_wp(uid), processing_dir=proc)

    monkeypatch.setattr("app.api.routes.files_routes.workspace_paths_for_user", wp)

    r = client.get("/api/processed-file", params={"rel_path": "stage1_normalized/hello.md"})
    assert r.status_code == 200
    assert "# Hi" in r.text


@pytest.mark.unit
def test_processed_file_local_404(client: TestClient, tmp_path, monkeypatch):
    from app.core.paths import workspace_paths_for_user as real_wp

    proc = tmp_path / "processing"
    proc.mkdir(parents=True)

    def wp(uid=None):
        return replace(real_wp(uid), processing_dir=proc)

    monkeypatch.setattr("app.api.routes.files_routes.workspace_paths_for_user", wp)

    r = client.get("/api/processed-file", params={"rel_path": "stage1_normalized/missing.md"})
    assert r.status_code == 404
