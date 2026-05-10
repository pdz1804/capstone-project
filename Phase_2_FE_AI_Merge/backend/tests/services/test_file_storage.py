"""Unit tests for app.storage — local backend, S3 URI parsing, factory, mocked S3 client."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.storage.service import (
    LocalFileStorage,
    S3FileStorage,
    get_file_storage,
    parse_s3_uri,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri,expected",
    [
        ("s3://my-bucket/input/a.pdf", ("my-bucket", "input/a.pdf")),
        ("s3://b/k", ("b", "k")),
        ("s3://b/path/to/key", ("b", "path/to/key")),
    ],
)
def test_parse_s3_uri_valid(uri: str, expected: tuple[str, str]):
    assert parse_s3_uri(uri) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "",
        "https://bucket/key",
        "s3://bucket",
        "s3://",
        "s3:///only-key-no-bucket",
    ],
)
def test_parse_s3_uri_invalid(uri: str):
    assert parse_s3_uri(uri) is None


@pytest.mark.unit
def test_local_storage_save_list_delete(tmp_path: Path):
    inp = tmp_path / "input"
    out = tmp_path / "output"
    store = LocalFileStorage(inp, out)

    row = store.save_upload("notes.txt", b"hello")
    assert row["name"] == "notes.txt"
    assert row["storage"] == "local"
    assert (inp / "notes.txt").read_bytes() == b"hello"

    listed = store.list_input_files()
    assert len(listed) == 1
    assert listed[0]["name"] == "notes.txt"

    assert store.delete(row["path"]) is True
    assert not (inp / "notes.txt").exists()
    assert store.list_input_files() == []


@pytest.mark.unit
def test_local_storage_upload_name_collision(tmp_path: Path):
    inp = tmp_path / "input"
    out = tmp_path / "output"
    store = LocalFileStorage(inp, out)
    store.save_upload("a.txt", b"1")
    row2 = store.save_upload("a.txt", b"2")
    assert row2["name"] == "a_1.txt"
    assert (inp / "a.txt").read_bytes() == b"1"
    assert (inp / "a_1.txt").read_bytes() == b"2"


@pytest.mark.unit
def test_local_storage_delete_rejects_path_outside_roots(tmp_path: Path):
    inp = tmp_path / "input"
    out = tmp_path / "output"
    other = tmp_path / "evil"
    other.mkdir()
    secret = other / "secret.txt"
    secret.write_text("x")
    store = LocalFileStorage(inp, out)
    assert store.delete(str(secret)) is False


@pytest.mark.unit
def test_local_storage_list_processed_with_preview(tmp_path: Path):
    inp = tmp_path / "input"
    out = tmp_path / "output"
    proc = out / "processing" / "stage1"
    proc.mkdir(parents=True)
    (proc / "readme.md").write_text("alpha" * 100, encoding="utf-8")
    store = LocalFileStorage(inp, out)
    rows = store.list_processed_files(include_preview=True)
    assert len(rows) == 1
    assert rows[0]["stage"] == "stage1"
    assert "preview" in rows[0]


@pytest.mark.unit
def test_local_resolve_pdf_path(tmp_path: Path):
    inp = tmp_path / "input"
    rag = tmp_path / "rag"
    rag.mkdir(parents=True)
    pdf = rag / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    store = LocalFileStorage(inp, tmp_path / "out")
    path, cleanup = store.resolve_pdf_path("doc", rag, inp)
    assert path == pdf
    assert cleanup is False


@pytest.mark.unit
def test_get_file_storage_local_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FILE_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_ORIGINALS_BUCKET", raising=False)
    monkeypatch.delenv("S3_PROCESSED_BUCKET", raising=False)
    s = get_file_storage()
    assert s.backend_name == "local"


@pytest.mark.unit
def test_get_file_storage_s3_requires_bucket(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_ORIGINALS_BUCKET", raising=False)
    monkeypatch.delenv("S3_PROCESSED_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="S3_BUCKET|S3_ORIGINALS"):
        get_file_storage()


@pytest.mark.unit
def test_get_file_storage_s3_dual_buckets(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("boto3")
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_ORIGINALS_BUCKET", "orig-dev")
    monkeypatch.setenv("S3_PROCESSED_BUCKET", "proc-dev")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_INPUT_PREFIX", raising=False)
    monkeypatch.delenv("S3_PROCESSING_PREFIX", raising=False)
    s = get_file_storage()
    assert s.backend_name == "s3"
    assert s.originals_bucket == "orig-dev"
    assert s.processed_bucket == "proc-dev"
    assert s.input_prefix == "users/default/"
    assert s.processing_prefix == "users/default/"


@pytest.mark.unit
def test_get_file_storage_s3_flat_prefix_when_isolation_off(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("boto3")
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_USER_ISOLATION", "false")
    monkeypatch.setenv("S3_ORIGINALS_BUCKET", "orig-dev")
    monkeypatch.setenv("S3_PROCESSED_BUCKET", "proc-dev")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_INPUT_PREFIX", raising=False)
    monkeypatch.delenv("S3_PROCESSING_PREFIX", raising=False)
    from app.storage.service import reset_file_storage_singleton

    reset_file_storage_singleton()
    s = get_file_storage()
    assert s.input_prefix == ""
    assert s.processing_prefix == ""


@pytest.mark.unit
def test_s3_storage_delete_validates_bucket_and_prefix():
    mock_client = MagicMock()
    store = S3FileStorage(
        originals_bucket="mybucket",
        processed_bucket="mybucket",
        input_prefix="input/",
        processing_prefix="processing/",
        local_input_dir=Path("/tmp/in"),
        local_output_dir=Path("/tmp/out"),
        region="us-east-1",
        s3_client=mock_client,
    )

    assert store.delete("s3://other/input/a.txt") is False
    assert store.delete("s3://mybucket/other/a.txt") is False
    assert store.delete("s3://mybucket/input/a.txt") is True
    assert mock_client.delete_object.call_count == 2
    mock_client.delete_object.assert_any_call(Bucket="mybucket", Key="input/a.txt.metadata.json")
    mock_client.delete_object.assert_any_call(Bucket="mybucket", Key="input/a.txt")


@pytest.mark.unit
def test_s3_storage_save_upload_puts_object():
    mock_client = MagicMock()
    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # 1) _head_exists → not found  2) after put_object → LastModified for response row
    mock_client.head_object.side_effect = [
        ClientError({"Error": {"Code": "404"}}, "HeadObject"),
        {"LastModified": fixed_time},
    ]

    store = S3FileStorage(
        originals_bucket="b",
        processed_bucket="b",
        input_prefix="in/",
        processing_prefix="proc/",
        local_input_dir=Path("/tmp/i"),
        local_output_dir=Path("/tmp/o"),
        s3_client=mock_client,
    )

    row = store.save_upload("f.txt", b"data")
    assert mock_client.put_object.call_count == 2
    mock_client.put_object.assert_any_call(Bucket="b", Key="in/f.txt", Body=b"data")
    sidecar_calls = [
        c for c in mock_client.put_object.call_args_list if c.kwargs.get("Key") == "in/f.txt.metadata.json"
    ]
    assert len(sidecar_calls) == 1
    assert sidecar_calls[0].kwargs["Bucket"] == "b"
    assert sidecar_calls[0].kwargs["ContentType"] == "application/json"
    assert row["path"] == "s3://b/in/f.txt"
    assert row["name"] == "f.txt"


@pytest.mark.unit
def test_s3_read_object():
    mock_client = MagicMock()
    body = MagicMock()
    body.read.return_value = b"\xff\xd8\xff"
    mock_client.get_object.return_value = {"Body": body, "ContentType": "image/jpeg"}

    store = S3FileStorage(
        originals_bucket="b",
        processed_bucket="b",
        input_prefix="in/",
        processing_prefix="proc/",
        local_input_dir=Path("/tmp/i"),
        local_output_dir=Path("/tmp/o"),
        s3_client=mock_client,
    )

    data, ct = store.read_object("b", "in/x.jpg")
    assert data == b"\xff\xd8\xff"
    assert ct == "image/jpeg"


@pytest.mark.unit
def test_s3_read_object_rejects_unknown_bucket():
    mock_client = MagicMock()
    store = S3FileStorage(
        originals_bucket="a",
        processed_bucket="b",
        input_prefix="",
        processing_prefix="",
        local_input_dir=Path("/tmp/i"),
        local_output_dir=Path("/tmp/o"),
        s3_client=mock_client,
    )
    with pytest.raises(ValueError, match="bucket not allowed"):
        store.read_object("other-bucket", "k")
