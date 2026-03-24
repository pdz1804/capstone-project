"""Paths and YAML configuration loading with environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

# backend/ is two levels above this file: app/core/paths.py
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_PATH = BACKEND_ROOT / "config" / "default.yaml"
INPUT_DIR = BACKEND_ROOT / "input"
OUTPUT_DIR = BACKEND_ROOT / "output"
RETRIEVAL_DIR = OUTPUT_DIR / "retrieval"
PROCESSING_DIR = OUTPUT_DIR / "processing"
RAG_READY_DIR = PROCESSING_DIR / "stage4_rag_ready"
BM25_PICKLE_PATH = RETRIEVAL_DIR / "bm25_index.pkl"
DOCUMENTS_JSON_PATH = RETRIEVAL_DIR / "documents.json"
IMAGE_META_PATH = OUTPUT_DIR / "image_retrieval" / "image_index_meta.json"


class AppPaths:
    backend_root = BACKEND_ROOT
    config_path = CONFIG_PATH
    input_dir = INPUT_DIR
    output_dir = OUTPUT_DIR
    retrieval_dir = RETRIEVAL_DIR
    processing_dir = PROCESSING_DIR
    rag_ready_dir = RAG_READY_DIR


def load_yaml_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merged_runtime_settings(yaml_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Apply environment overrides used in production (Qdrant, SageMaker)."""
    cfg = dict(yaml_config) if yaml_config is not None else load_yaml_config()
    q = cfg.setdefault("qdrant", {})
    inf = cfg.setdefault("inference", {})

    if os.getenv("QDRANT_MODE"):
        q["mode"] = os.getenv("QDRANT_MODE", "").strip().lower()
    if os.getenv("QDRANT_HOST"):
        q["host"] = os.getenv("QDRANT_HOST", "")
    if os.getenv("QDRANT_PORT"):
        q["port"] = int(os.getenv("QDRANT_PORT", "6333"))
    if os.getenv("QDRANT_URL"):
        q["url"] = os.getenv("QDRANT_URL", "")
    if os.getenv("QDRANT_API_KEY"):
        q["api_key"] = os.getenv("QDRANT_API_KEY", "")
    if os.getenv("QDRANT_TEXT_COLLECTION"):
        q["text_collection"] = os.getenv("QDRANT_TEXT_COLLECTION", "")
    if os.getenv("QDRANT_IMAGE_COLLECTION"):
        q["image_collection"] = os.getenv("QDRANT_IMAGE_COLLECTION", "")

    sm = os.getenv("USE_AWS_SAGEMAKER_INFERENCE", "").strip().lower() in ("1", "true", "yes")
    if sm:
        inf["use_aws_sagemaker"] = True
    if os.getenv("AWS_REGION"):
        inf["aws_region"] = os.getenv("AWS_REGION", "")
    if os.getenv("SAGEMAKER_ENDPOINT_NAME"):
        inf["sagemaker_endpoint_name"] = os.getenv("SAGEMAKER_ENDPOINT_NAME", "")

    return cfg


def ensure_data_dirs() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)
