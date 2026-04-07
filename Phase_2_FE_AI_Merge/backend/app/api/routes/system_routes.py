"""Runtime probes (inference + vector store)."""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.api.schemas import InferenceProbeResponse
from app.core.paths import merged_runtime_settings

router = APIRouter(prefix="/api/system", tags=["system"])


def _effective_sagemaker(cfg: dict) -> bool:
    if os.getenv("USE_AWS_SAGEMAKER_INFERENCE", "").strip().lower() in ("1", "true", "yes"):
        return True
    inf = cfg.get("inference", {}) or {}
    v = inf.get("use_aws_sagemaker")
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


def _effective_sagemaker_docling(cfg: dict) -> bool:
    if os.getenv("USE_AWS_SAGEMAKER_DOCLING", "").strip().lower() in ("1", "true", "yes"):
        return True
    inf = cfg.get("inference", {}) or {}
    v = inf.get("use_aws_sagemaker_docling")
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


def _effective_sagemaker_whisper(cfg: dict) -> bool:
    if os.getenv("USE_AWS_SAGEMAKER_WHISPER", "").strip().lower() in ("1", "true", "yes"):
        return True
    inf = cfg.get("inference", {}) or {}
    v = inf.get("use_aws_sagemaker_whisper")
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


@router.get("/inference", response_model=InferenceProbeResponse)
def inference_probe():
    cfg = merged_runtime_settings()
    inf = cfg.get("inference", {}) or {}
    q = cfg.get("qdrant", {}) or {}
    gen = cfg.get("generation", {}) or {}
    use_sm = _effective_sagemaker(cfg)
    use_doc = _effective_sagemaker_docling(cfg)
    use_whisper = _effective_sagemaker_whisper(cfg)
    return InferenceProbeResponse(
        use_aws_sagemaker_inference=use_sm,
        sagemaker_endpoint_name=inf.get("sagemaker_endpoint_name"),
        use_aws_sagemaker_docling=use_doc,
        sagemaker_docling_endpoint_name=inf.get("sagemaker_docling_endpoint_name"),
        use_aws_sagemaker_whisper=use_whisper,
        sagemaker_whisper_endpoint_name=inf.get("sagemaker_whisper_endpoint_name"),
        aws_region=inf.get("aws_region"),
        qdrant_mode=str(q.get("mode", "docker")),
        text_collection=str(q.get("text_collection", "edu_text_chunks")),
        image_collection=str(q.get("image_collection", "edu_image_pages")),
        generation_provider=str(gen.get("provider", "")) or None,
    )
