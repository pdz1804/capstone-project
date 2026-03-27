"""Tests for processed markdown context (insights source)."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.processed_markdown_service import gather_processed_markdown_context


@pytest.fixture
def fake_processing(tmp_path: Path) -> Path:
    root = tmp_path / "processing"
    doc = root / "stage3_document_processed" / "CourseA"
    doc.mkdir(parents=True)
    (doc / "CourseA.md").write_text("# Chapter One\n\nHello world.", encoding="utf-8")
    (doc / "table_000.md").write_text("|a|b|", encoding="utf-8")
    return root


def test_gather_scoped_to_document(fake_processing: Path) -> None:
    ws = SimpleNamespace(processing_dir=fake_processing)
    with patch("app.services.processed_markdown_service.workspace_paths_for_user", return_value=ws):
        ctx = gather_processed_markdown_context("default", "CourseA", 50_000)
    assert "Chapter One" in ctx
    assert "table_000.md" in ctx or "File:" in ctx
    assert "stage3_document_processed" in ctx


def test_gather_all_documents_when_no_document_id(fake_processing: Path) -> None:
    ws = SimpleNamespace(processing_dir=fake_processing)
    with patch("app.services.processed_markdown_service.workspace_paths_for_user", return_value=ws):
        ctx = gather_processed_markdown_context("default", None, 50_000)
    assert "Hello world" in ctx


def test_stage4_fallback_when_stage3_empty(tmp_path: Path) -> None:
    root = tmp_path / "processing"
    s4 = root / "stage4_rag_ready" / "OnlyHere"
    s4.mkdir(parents=True)
    (s4 / "OnlyHere.md").write_text("# From stage4", encoding="utf-8")
    ws = SimpleNamespace(processing_dir=root)
    with patch("app.services.processed_markdown_service.workspace_paths_for_user", return_value=ws):
        ctx = gather_processed_markdown_context("default", "OnlyHere", 50_000)
    assert "From stage4" in ctx


def test_rejects_path_traversal_document_id(fake_processing: Path) -> None:
    ws = SimpleNamespace(processing_dir=fake_processing)
    with patch("app.services.processed_markdown_service.workspace_paths_for_user", return_value=ws):
        ctx = gather_processed_markdown_context("default", "../evil", 1000)
    assert ctx == ""
