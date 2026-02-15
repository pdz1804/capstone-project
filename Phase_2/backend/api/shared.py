"""
Shared constants, helpers, and models used across route modules.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import yaml
from pydantic import BaseModel

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.unified_rag_pipeline import UnifiedRAGPipeline, UnifiedRAGConfig
from src.generation.generator import GenerationConfig
from src.processor.pipeline import PipelineConfig

logger = logging.getLogger(__name__)

# ── Directory constants ───────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_PATH = BASE_DIR / "config" / "default.yaml"

# Ensure directories exist
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Pydantic models ──────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    retriever_type: str = "hybrid"
    include_images: bool = True
    images_for_generation: int = 5


class FileDeleteRequest(BaseModel):
    path: str


class ProcessingStatus(BaseModel):
    ready: bool
    indexed_docs: int
    image_pages: int
    text_index: Optional[Dict[str, Any]] = None
    image_index: Optional[Dict[str, Any]] = None


# ── Helper functions ─────────────────────────────────────
def get_file_info(file_path: Path) -> Dict[str, Any]:
    """Get file information."""
    stat = file_path.stat()
    size_bytes = stat.st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    return {
        "name": file_path.name,
        "path": str(file_path),
        "size": size_str,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "type": file_path.suffix.lower()
    }


def load_yaml_config() -> Dict[str, Any]:
    """Load the pipeline YAML config."""
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f) or {}


def build_runtime_config(yaml_config: Dict[str, Any], enable_generation: bool = True) -> UnifiedRAGConfig:
    """
    Build a UnifiedRAGConfig from YAML for request-scoped pipelines.
    Mirrors the retrieval-related options used in CLI/index.
    """
    yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})
    yaml_image_retrieval_enabled = yaml_config.get('image_retrieval', {}).get('enabled', False)
    yaml_reranker = yaml_config.get('text_retrieval', {}).get('reranker', {})

    rag_mode = yaml_config.get('pipeline', {}).get('rag_mode', 'text')
    enable_image_retrieval = rag_mode in ["image", "both"] or yaml_image_retrieval_enabled

    reranker_enabled = yaml_reranker.get('enabled', False)
    reranker_model = yaml_reranker.get('model') if reranker_enabled else None

    generation_config = GenerationConfig(base_dir=str(BASE_DIR))

    return UnifiedRAGConfig(
        enable_processing=False,
        enable_retrieval=True,
        enable_generation=enable_generation,
        enable_evaluation=False,
        processing_config=PipelineConfig(),
        rag_mode=rag_mode,
        retrieval_methods=yaml_config.get('pipeline', {}).get('retrievers', ['bm25', 'dense', 'hybrid']),
        enable_reranker=reranker_enabled,
        reranker_model=reranker_model,
        enable_image_retrieval=enable_image_retrieval,
        image_retrieval_methods=yaml_config.get('image_retrieval', {}).get('methods', ['colqwen']),
        colqwen_model=yaml_colqwen.get('model', 'vidore/colqwen2-v1.0'),
        colqwen_dtype=yaml_colqwen.get('dtype', 'bfloat16'),
        colqwen_quantization=yaml_colqwen.get('quantization', '8bit'),
        colqwen_pdf_dpi=yaml_colqwen.get('pdf_dpi', 150),
        generation_config=generation_config
    )
