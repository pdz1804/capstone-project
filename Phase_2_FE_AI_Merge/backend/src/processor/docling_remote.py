"""
Optional SageMaker Docling stage (Stage 3).

Contract for the remote endpoint body (JSON):
  {
    "operation": "process-document",
    "filename": "<name>",
    "content_base64": "<bytes>"
  }

Response (JSON):
  {
    "markdown": "<full markdown text>",
    "additional_files": { "docling_additional/rel/path.png": "<base64>", ... }  // optional
  }
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def should_use_sagemaker_docling(runtime_yaml: Optional[Dict[str, Any]]) -> bool:
    if _truthy_env("USE_AWS_SAGEMAKER_DOCLING"):
        return True
    if not runtime_yaml:
        return False
    inf = runtime_yaml.get("inference") or {}
    v = inf.get("use_aws_sagemaker_docling")
    if isinstance(v, str):
        if v.strip().lower() in ("1", "true", "yes"):
            return True
    elif v:
        return True
    doc = (runtime_yaml.get("processing") or {}).get("document") or {}
    backend = (doc.get("docling_backend") or "local").strip().lower()
    if backend == "sagemaker":
        return True
    if (doc.get("docling_remote") or "").strip().lower() in ("1", "true", "yes", "sagemaker"):
        return True
    return False


def _endpoint_and_region(runtime_yaml: Dict[str, Any]) -> tuple[str, str]:
    inf = runtime_yaml.get("inference") or {}
    ep = (
        os.getenv("SAGEMAKER_DOCLING_ENDPOINT_NAME", "").strip()
        or (inf.get("sagemaker_docling_endpoint_name") or "").strip()
    )
    region = (
        os.getenv("AWS_REGION", "").strip()
        or (inf.get("aws_region") or "us-east-1").strip()
    )
    return ep, region


def invoke_sagemaker_docling(file_path: Path, runtime_yaml: Dict[str, Any]) -> Dict[str, Any]:
    ep, region = _endpoint_and_region(runtime_yaml)
    if not ep:
        raise RuntimeError(
            "SageMaker Docling is enabled but sagemaker_docling_endpoint_name / "
            "SAGEMAKER_DOCLING_ENDPOINT_NAME is empty."
        )
    import boto3

    raw = file_path.read_bytes()
    payload = {
        "operation": "process-document",
        "filename": file_path.name,
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }
    rt = boto3.client("sagemaker-runtime", region_name=region)
    resp = rt.invoke_endpoint(
        EndpointName=ep,
        ContentType="application/json",
        Accept="application/json",
        Body=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(resp["Body"].read().decode("utf-8"))


def write_docling_outputs_from_sagemaker(final_processed: Path, file_path: Path, data: Dict[str, Any]) -> None:
    stem = file_path.stem
    out_folder = final_processed / stem
    out_folder.mkdir(parents=True, exist_ok=True)
    md = (data.get("markdown") or data.get("file_md") or "").strip()
    if not md:
        raise ValueError("SageMaker Docling response missing markdown")
    (out_folder / f"{stem}.md").write_text(md, encoding="utf-8")
    addl = data.get("additional_files") or {}
    if isinstance(addl, dict):
        for rel, b64 in addl.items():
            rel_s = str(rel).replace("\\", "/").lstrip("/")
            if ".." in rel_s or rel_s.startswith("/"):
                logger.warning("Skipping unsafe additional_files path: %s", rel)
                continue
            target = out_folder / rel_s
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(str(b64)))
    logger.info("Wrote SageMaker Docling output under %s", out_folder)
