"""Structured processing tree snapshot (local layout)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.service import LocalFileStorage, reset_file_storage_singleton


@pytest.mark.unit
def test_build_processed_documents_snapshot_groups_stage4(tmp_path, monkeypatch):
    from app.services import processed_documents_service as pds

    inp = tmp_path / "input"
    out = tmp_path / "output"
    proc = out / "processing"
    (proc / "stage4_rag_ready" / "MyBook").mkdir(parents=True)
    (proc / "stage4_rag_ready" / "MyBook" / "chunk.md").write_text("hello", encoding="utf-8")
    (proc / "pipeline_stats.json").write_text("{}", encoding="utf-8")

    def fake_paths(uid=None):
        class P:
            user_id = "default"
            processing_dir = proc

        return P()

    def fake_storage(uid=None):
        return LocalFileStorage(inp, out)

    monkeypatch.setattr(pds, "workspace_paths_for_user", fake_paths)
    monkeypatch.setattr(pds, "get_file_storage", fake_storage)
    reset_file_storage_singleton()

    snap = pds.build_processed_documents_snapshot("default", include_preview=False)
    assert snap["document_count"] == 1
    assert snap["named_document_folders"] == 1
    assert len(snap["documents"]) == snap["document_count"]
    assert snap["documents"][0]["id"] == "MyBook"
    assert snap["documents"][0]["stages"]["stage4_rag_ready"]["file_count"] == 1
    assert snap["root_file_count"] == 1
    assert snap["stage_totals"]["stage4_rag_ready"] == 1


@pytest.mark.unit
def test_document_count_includes_pipeline_wide_group(tmp_path, monkeypatch):
    """Shared bucket is appended to documents[]; document_count must match len(documents)."""
    from app.services import processed_documents_service as pds

    inp = tmp_path / "input"
    out = tmp_path / "output"
    proc = out / "processing"
    (proc / "stage4_rag_ready" / "BookA").mkdir(parents=True)
    (proc / "stage4_rag_ready" / "BookA" / "a.md").write_text("x", encoding="utf-8")
    (proc / "stage1_normalized" / "normalization_metadata").mkdir(parents=True)
    (proc / "stage1_normalized" / "normalization_metadata" / "normalization_stats.json").write_text("{}", encoding="utf-8")

    class P:
        user_id = "default"
        processing_dir = proc

    monkeypatch.setattr(pds, "workspace_paths_for_user", lambda uid=None: P())
    monkeypatch.setattr(pds, "get_file_storage", lambda uid=None: LocalFileStorage(inp, out))
    reset_file_storage_singleton()

    snap = pds.build_processed_documents_snapshot("default", include_preview=False)
    assert snap["named_document_folders"] == 1
    assert snap["document_count"] == 2
    assert len(snap["documents"]) == 2
    ids = {d["id"] for d in snap["documents"]}
    assert "BookA" in ids
    assert pds._SHARED_SENTINEL in ids


@pytest.mark.unit
def test_processed_documents_api_route(client, tmp_path, monkeypatch):
    """Smoke: endpoint returns expected keys when processing dir is redirected."""
    from dataclasses import replace

    from app.core.paths import workspace_paths_for_user as real_wp
    from app.services import processed_documents_service as pds

    proc = tmp_path / "processing"
    (proc / "stage1_normalized").mkdir(parents=True)
    (proc / "stage1_normalized" / "note.md").write_text("x", encoding="utf-8")

    def wp(uid=None):
        return replace(real_wp(uid), processing_dir=Path(proc))

    monkeypatch.setattr(pds, "workspace_paths_for_user", wp)

    r = client.get("/api/processed-documents")
    assert r.status_code == 200
    data = r.json()
    assert "documents" in data and "stage_order" in data
    assert "stage_totals" in data and "input_file_count" in data
    assert "named_document_folders" in data and "count_hints" in data
