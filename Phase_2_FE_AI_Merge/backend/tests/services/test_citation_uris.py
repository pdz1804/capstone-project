"""S3 URI mapping for citation metadata."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.citation_uris import enrich_chunk_documents_storage_uris, sanitize_metadata_for_api
from app.storage.service import S3FileStorage


@pytest.mark.unit
def test_s3_uri_for_local_under_processing(tmp_path: Path):
    out = tmp_path / "output"
    proc = out / "processing"
    rag = proc / "stage4_rag_ready" / "MyDoc"
    rag.mkdir(parents=True)
    md = rag / "MyDoc.md"
    md.write_text("# x", encoding="utf-8")

    mock = MagicMock()
    store = S3FileStorage(
        originals_bucket="o",
        processed_bucket="p",
        input_prefix="in/",
        processing_prefix="proc/",
        local_input_dir=tmp_path / "input",
        local_output_dir=out,
        s3_client=mock,
    )
    uri = store.uri_for_local_under_processing(md)
    assert uri == "s3://p/proc/stage4_rag_ready/MyDoc/MyDoc.md"


@pytest.mark.unit
def test_enrich_documents_sets_storage_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    out = tmp_path / "output"
    proc = out / "processing"
    rag = proc / "stage4_rag_ready" / "Doc"
    rag.mkdir(parents=True)
    md = rag / "Doc.md"
    md.write_text("hi", encoding="utf-8")

    mock_client = MagicMock()
    store = S3FileStorage(
        originals_bucket="orig",
        processed_bucket="proc",
        input_prefix="in/",
        processing_prefix="pr/",
        local_input_dir=tmp_path / "input",
        local_output_dir=out,
        s3_client=mock_client,
    )

    monkeypatch.setattr(
        "app.services.citation_uris.get_file_storage",
        lambda _uid=None: store,
    )

    docs = [
        {
            "id": "c1",
            "text": "chunk",
            "source": str(md),
            "metadata": {"original_file": str(md)},
        }
    ]
    enrich_chunk_documents_storage_uris(docs, user_id="default")
    assert docs[0]["metadata"].get("storage_uri") == "s3://proc/pr/stage4_rag_ready/Doc/Doc.md"
    assert docs[0]["metadata"].get("storage_backend") == "s3"


@pytest.mark.unit
def test_sanitize_metadata_strips_local_paths_when_storage_uri():
    meta = {
        "storage_uri": "s3://b/k/doc.md",
        "storage_backend": "s3",
        "original_file": r"C:\Temp\machine\doc.md",
        "source_path": r"C:\Temp\page.png",
    }
    out = sanitize_metadata_for_api(meta)
    assert out.get("storage_uri") == "s3://b/k/doc.md"
    assert "original_file" not in out
    assert "source_path" not in out
