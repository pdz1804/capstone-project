"""Optional SageMaker Whisper invocation helpers for Stage 2 media ASR."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _bool_like(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def should_use_sagemaker_whisper(
    runtime_yaml: Optional[Dict[str, Any]] = None,
    media_config: Any | None = None,
) -> bool:
    if _truthy_env("USE_AWS_SAGEMAKER_WHISPER"):
        return True
    if media_config is not None and _bool_like(getattr(media_config, "use_aws_sagemaker_whisper", False)):
        return True
    if not runtime_yaml:
        return False
    inf = runtime_yaml.get("inference") or {}
    return _bool_like(inf.get("use_aws_sagemaker_whisper"))


def _endpoint_and_region(runtime_yaml: Optional[Dict[str, Any]], media_config: Any | None) -> tuple[str, str]:
    inf = (runtime_yaml or {}).get("inference") or {}

    endpoint = (
        os.getenv("SAGEMAKER_WHISPER_ENDPOINT_NAME", "").strip()
        or (getattr(media_config, "sagemaker_whisper_endpoint_name", "") or "").strip()
        or (inf.get("sagemaker_whisper_endpoint_name") or "").strip()
        or os.getenv("SAGEMAKER_ENDPOINT_NAME", "").strip()
        or (inf.get("sagemaker_endpoint_name") or "").strip()
    )
    region = (
        os.getenv("AWS_REGION", "").strip()
        or (getattr(media_config, "aws_region", "") or "").strip()
        or (inf.get("aws_region") or "").strip()
        or "us-west-2"
    )
    return endpoint, region


def invoke_sagemaker_whisper(
    audio_path: Path,
    *,
    language: str | None = None,
    word_timestamps: bool = True,
    runtime_yaml: Optional[Dict[str, Any]] = None,
    media_config: Any | None = None,
) -> Dict[str, Any]:
    endpoint_name, region = _endpoint_and_region(runtime_yaml, media_config)
    if not endpoint_name:
        raise RuntimeError(
            "SageMaker Whisper is enabled but endpoint name is empty. "
            "Set SAGEMAKER_WHISPER_ENDPOINT_NAME (or fallback SAGEMAKER_ENDPOINT_NAME)."
        )

    import boto3
    from botocore.config import Config

    payload = {
        "operation": "transcribe-audio",
        "filename": audio_path.name,
        "audio_base64": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
        "language": language,
        "word_timestamps": bool(word_timestamps),
    }

    read_timeout = int(os.getenv("SAGEMAKER_RUNTIME_READ_TIMEOUT_SECONDS", "420"))
    connect_timeout = int(os.getenv("SAGEMAKER_RUNTIME_CONNECT_TIMEOUT_SECONDS", "10"))
    rt = boto3.client(
        "sagemaker-runtime",
        region_name=region,
        config=Config(
            read_timeout=read_timeout,
            connect_timeout=connect_timeout,
            retries={"max_attempts": 0},
        ),
    )
    resp = rt.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        Body=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(resp["Body"].read().decode("utf-8"))

