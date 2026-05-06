from typing import Any, Dict

import yaml
from fastapi import APIRouter

from app.core.paths import CONFIG_PATH, merged_runtime_settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}
        merged = merged_runtime_settings(config_dict)
        pipe = merged.get("pipeline", {}) or {}
        tr = merged.get("text_retrieval", {}) or {}
        ir = merged.get("image_retrieval", {}) or {}
        inf = merged.get("inference", {}) or {}
        q = merged.get("qdrant", {}) or {}
        gen = merged.get("generation", {}) or {}
        proc_doc = (merged.get("processing", {}) or {}).get("document", {}) or {}
        return {
            "config_path": str(CONFIG_PATH),
            "config": merged,
            "key_settings": {
                "pipeline_mode": pipe.get("mode", "unknown"),
                "rag_mode": pipe.get("rag_mode", "unknown"),
                "text_embedding_model": tr.get("embedding_model", "unknown"),
                "retrieval_methods": tr.get("methods", []),
                "image_retrieval_enabled": ir.get("enabled", False),
                "colqwen_model": (ir.get("colqwen", {}) or {}).get("model", "unknown"),
                "qdrant_mode": q.get("mode", "docker"),
                "text_collection": q.get("text_collection"),
                "image_collection": q.get("image_collection"),
                "use_aws_sagemaker_inference": bool(inf.get("use_aws_sagemaker")),
                "sagemaker_endpoint": inf.get("sagemaker_endpoint_name"),
                "use_aws_sagemaker_docling": bool(inf.get("use_aws_sagemaker_docling")),
                "sagemaker_docling_endpoint": inf.get("sagemaker_docling_endpoint_name"),
                "use_aws_sagemaker_whisper": bool(inf.get("use_aws_sagemaker_whisper")),
                "sagemaker_whisper_endpoint": inf.get("sagemaker_whisper_endpoint_name"),
                "docling_backend": proc_doc.get("docling_backend", "sagemaker"),
                "generation_provider": gen.get("provider"),
                "generation_model": gen.get("model"),
            },
        }
    except Exception as e:
        return {"error": str(e), "config_path": str(CONFIG_PATH)}
