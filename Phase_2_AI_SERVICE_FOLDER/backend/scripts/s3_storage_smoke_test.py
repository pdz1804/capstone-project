#!/usr/bin/env python3
"""
Live S3 smoke test for dual-bucket storage (originals + processed).

Requires: boto3, AWS credentials (env, profile, or instance role).

  set S3_ORIGINALS_BUCKET=ai-service-originals-dev
  set S3_PROCESSED_BUCKET=ai-service-processed-dev
  set AWS_REGION=ap-southeast-1   (or your region)

Run from repo root or backend:

  python scripts/s3_storage_smoke_test.py
"""

from __future__ import annotations

import os
import sys
import uuid

KEY_MARKER = ".ai-service-smoke"


def main() -> int:
    orig = os.environ.get("S3_ORIGINALS_BUCKET", "").strip()
    proc = os.environ.get("S3_PROCESSED_BUCKET", "").strip()
    if not orig or not proc:
        print(
            "Set S3_ORIGINALS_BUCKET and S3_PROCESSED_BUCKET (e.g. ai-service-originals-dev / ai-service-processed-dev).",
            file=sys.stderr,
        )
        return 2

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("Install boto3: pip install boto3", file=sys.stderr)
        return 2

    client = boto3.client("s3")
    token = uuid.uuid4().hex[:10]
    key_o = f"smoke{KEY_MARKER}-{token}.txt"
    key_p = f"smoke{KEY_MARKER}-{token}.md"

    try:
        client.put_object(Bucket=orig, Key=key_o, Body=b"originals plane ok")
        client.head_object(Bucket=orig, Key=key_o)

        client.put_object(Bucket=proc, Key=key_p, Body=b"# processed plane ok\n")
        client.head_object(Bucket=proc, Key=key_p)

        body = client.get_object(Bucket=orig, Key=key_o)["Body"].read()
        assert body == b"originals plane ok"

        print(f"OK: wrote/read originals s3://{orig}/{key_o}")
        print(f"OK: wrote/read processed s3://{proc}/{key_p}")
    except ClientError as e:
        print(f"AWS error: {e}", file=sys.stderr)
        return 1
    finally:
        for bucket, key in ((orig, key_o), (proc, key_p)):
            try:
                client.delete_object(Bucket=bucket, Key=key)
            except ClientError:
                pass

    # Optional: same paths as the FastAPI S3FileStorage (empty prefixes)
    os.environ.setdefault("FILE_STORAGE_BACKEND", "s3")
    os.environ["S3_ORIGINALS_BUCKET"] = orig
    os.environ["S3_PROCESSED_BUCKET"] = proc
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from app.storage.service import reset_file_storage_singleton, S3FileStorage
    from pathlib import Path

    reset_file_storage_singleton()
    tmp = Path(backend_root) / "input" / ".smoke_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    store = S3FileStorage(
        originals_bucket=orig,
        processed_bucket=proc,
        input_prefix="",
        processing_prefix="",
        local_input_dir=tmp,
        local_output_dir=tmp.parent.parent / "output",
        region=os.environ.get("AWS_REGION", "").strip() or None,
    )
    row = store.save_upload(f"smoke-upload{KEY_MARKER}-{token}.txt", b"via S3FileStorage")
    assert orig in row["path"]
    listed = store.list_input_files()
    assert any(KEY_MARKER in r["name"] for r in listed)
    assert store.delete(row["path"]) is True

    print("OK: S3FileStorage save_upload / list_input_files / delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
