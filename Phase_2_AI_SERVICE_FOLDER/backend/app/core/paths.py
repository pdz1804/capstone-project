"""Paths and YAML configuration loading with environment overrides."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
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


def file_storage_backend() -> str:
    return os.getenv("FILE_STORAGE_BACKEND", "local").strip().lower()


def is_s3_storage_backend() -> bool:
    return file_storage_backend() == "s3"


def sanitize_storage_user_id(raw: str | None) -> str:
    """Safe path segment + S3 prefix segment (alphanumeric, dot, underscore, hyphen)."""
    s = (raw or "").strip() or os.getenv("DEFAULT_STORAGE_USER_ID", "default").strip() or "default"
    out: list[str] = []
    for c in s[:128]:
        if c.isalnum() or c in "._-":
            out.append(c)
    t = "".join(out)
    return t or "default"


def should_isolate_qdrant_by_user() -> bool:
    """When true, text/image collection names get a per-user suffix (multi-tenant Qdrant)."""
    v = os.getenv("QDRANT_ISOLATE_BY_USER", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False


def qdrant_safe_suffix(sanitized_user_id: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9_]", "_", sanitized_user_id)[:48].strip("_")
    return t or "default"


def qdrant_collection_names_for_user(
    base_text_collection: str,
    base_image_collection: str,
    sanitized_user_id: str,
) -> tuple[str, str]:
    if not should_isolate_qdrant_by_user():
        return base_text_collection, base_image_collection
    suf = qdrant_safe_suffix(sanitized_user_id)
    return f"{base_text_collection}_{suf}", f"{base_image_collection}_{suf}"


@dataclass(frozen=True)
class WorkspacePaths:
    """All on-disk locations for one storage user (local repo dirs or ephemeral temp when S3)."""

    user_id: str
    input_dir: Path
    output_dir: Path
    processing_dir: Path
    rag_ready_dir: Path
    retrieval_dir: Path
    documents_json_path: Path
    bm25_pickle_path: Path
    image_retrieval_root: Path
    image_meta_path: Path

    @property
    def pipeline_output_dir(self) -> Path:
        """Parent of stage1_normalized… (same as processing_dir for DocumentProcessingPipeline)."""
        return self.processing_dir


def workspace_paths_for_user(user_id: str | None = None) -> WorkspacePaths:
    """
    Local backend: shared repo ``backend/input`` and ``backend/output`` (user_id ignored).

    S3 backend: ephemeral workspace under the system temp dir — nothing under the repo tree.
    """
    uid = sanitize_storage_user_id(user_id)
    if not is_s3_storage_backend():
        out = BACKEND_ROOT / "output"
        proc = out / "processing"
        retr = out / "retrieval"
        img_root = out / "image_retrieval"
        return WorkspacePaths(
            user_id=uid,
            input_dir=BACKEND_ROOT / "input",
            output_dir=out,
            processing_dir=proc,
            rag_ready_dir=proc / "stage4_rag_ready",
            retrieval_dir=retr,
            documents_json_path=retr / "documents.json",
            bm25_pickle_path=retr / "bm25_index.pkl",
            image_retrieval_root=img_root,
            image_meta_path=img_root / "image_index_meta.json",
        )

    base = Path(os.getenv("LOCAL_WORKSPACE_ROOT", tempfile.gettempdir())).resolve()
    root = base / "phase2_ai_workspace" / uid
    out = root / "output"
    proc = out / "processing"
    retr = out / "retrieval"
    img_root = out / "image_retrieval"
    return WorkspacePaths(
        user_id=uid,
        input_dir=root / "input",
        output_dir=out,
        processing_dir=proc,
        rag_ready_dir=proc / "stage4_rag_ready",
        retrieval_dir=retr,
        documents_json_path=retr / "documents.json",
        bm25_pickle_path=retr / "bm25_index.pkl",
        image_retrieval_root=img_root,
        image_meta_path=img_root / "image_index_meta.json",
    )


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


def ensure_data_dirs(user_id: str | None = None) -> None:
    """
    Create directories required for the active storage mode.

    Local: ``backend/input``, ``backend/output``, and retrieval layout under output.

    S3: only the ephemeral workspace for the given user (default ``default``) under the
    system temp tree — no ``input``/``output`` folders next to source code.
    """
    paths = workspace_paths_for_user(user_id)
    paths.input_dir.mkdir(parents=True, exist_ok=True)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.processing_dir.mkdir(parents=True, exist_ok=True)
    paths.retrieval_dir.mkdir(parents=True, exist_ok=True)
    paths.image_retrieval_root.mkdir(parents=True, exist_ok=True)
