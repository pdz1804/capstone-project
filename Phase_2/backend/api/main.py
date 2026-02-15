"""
FastAPI Backend for RAG Pipeline Demo

Provides REST API endpoints for:
- File upload and management
- Document processing
- Indexing
- Search / Query
"""

import os

# ── Early PyTorch config for low-SM GPUs (must be set before any torch import) ──
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import json
import logging
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared import OUTPUT_DIR, CONFIG_PATH

# ── Route modules ────────────────────────────────────────
from routes.files import router as files_router
from routes.pipeline import router as pipeline_router
from routes.search import router as search_router
from routes.images import router as images_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    try:
        logger.info("API startup")
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
    yield
    logger.info("Shutting down API...")


# Initialize FastAPI app
app = FastAPI(
    title="RAG Pipeline API",
    description="API for Multimodal Retrieval-Augmented Generation Pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include route modules ─────────────────────────────────
app.include_router(files_router)
app.include_router(pipeline_router)
app.include_router(search_router)
app.include_router(images_router)


# ── Lightweight endpoints (kept in main) ──────────────────

@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    Get pipeline status – lightweight version that reads metadata files
    without loading the full pipeline (optimized for frequent polling).
    """
    try:
        status = {
            "ready": False,
            "indexed_docs": 0,
            "image_pages": 0,
            "text_index": None,
            "image_index": None
        }

        # Check text index metadata
        retrieval_dir = OUTPUT_DIR / "retrieval"
        if retrieval_dir.exists():
            docs_file = retrieval_dir / "documents.json"
            if docs_file.exists():
                try:
                    with open(docs_file, 'r', encoding='utf-8') as f:
                        documents = json.load(f)

                    retrievers = []
                    for subdir in retrieval_dir.iterdir():
                        if subdir.is_dir() and subdir.name in ['bm25', 'dense', 'hybrid']:
                            if subdir.name == 'bm25' and (subdir / "bm25_index.pkl").exists():
                                retrievers.append('bm25')
                            elif subdir.name == 'dense' and (subdir / "faiss_index.bin").exists():
                                retrievers.append('dense')
                            elif subdir.name == 'hybrid' and (subdir / "bm25_index.pkl").exists() and (subdir / "faiss_index.bin").exists():
                                retrievers.append('hybrid')

                    sources = {doc.get('source', '') for doc in documents if doc.get('source')}

                    status["text_index"] = {
                        "chunks": len(documents),
                        "docs": len(sources),
                        "retrievers": retrievers
                    }
                    status["indexed_docs"] = len(documents)
                    status["ready"] = True
                except Exception as e:
                    logger.debug(f"Could not read text index metadata: {e}")

        # Check image index metadata
        image_retrieval_dir = OUTPUT_DIR / "image_retrieval"
        if image_retrieval_dir.exists():
            meta_file = image_retrieval_dir / "image_index_meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        image_meta = json.load(f)

                    colqwen_meta = image_retrieval_dir / "colqwen" / "colqwen_meta.json"
                    total_pages = 0
                    if colqwen_meta.exists():
                        with open(colqwen_meta, 'r', encoding='utf-8') as f:
                            cq_meta = json.load(f)
                        total_pages = cq_meta.get('num_pages', 0)

                    status["image_index"] = {
                        "pages": total_pages,
                        "retrievers": image_meta.get('retrievers', [])
                    }
                    status["image_pages"] = total_pages
                    if total_pages > 0:
                        status["ready"] = True
                except Exception as e:
                    logger.debug(f"Could not read image index metadata: {e}")

        return status
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"ready": False, "indexed_docs": 0, "image_pages": 0, "error": str(e)}


@app.get("/api/config")
async def get_config() -> Dict[str, Any]:
    """Get current pipeline configuration."""
    try:
        import yaml
        with open(CONFIG_PATH, 'r') as f:
            config_dict = yaml.safe_load(f)
        return {
            "config_path": str(CONFIG_PATH),
            "config": config_dict,
            "key_settings": {
                "pipeline_mode": config_dict.get("pipeline", {}).get("mode", "unknown"),
                "rag_mode": config_dict.get("pipeline", {}).get("rag_mode", "unknown"),
                "enable_processing": config_dict.get("pipeline", {}).get("enable_processing", False),
                "enable_retrieval": config_dict.get("pipeline", {}).get("enable_retrieval", False),
                "enable_generation": config_dict.get("pipeline", {}).get("enable_generation", False),
                "image_retrieval_enabled": config_dict.get("image_retrieval", {}).get("enabled", False),
                "colqwen_model": config_dict.get("image_retrieval", {}).get("colqwen", {}).get("model", "unknown"),
                "colqwen_quantization": config_dict.get("image_retrieval", {}).get("colqwen", {}).get("quantization", "none"),
                "text_embedding_model": config_dict.get("text_retrieval", {}).get("embedding_model", "unknown"),
                "retrieval_methods": config_dict.get("text_retrieval", {}).get("methods", [])
            }
        }
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {"error": str(e), "config_path": str(CONFIG_PATH)}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/health")
async def health_check_simple():
    """Simple health check endpoint (alias for /api/health)."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path

    base_dir = Path(__file__).parent.parent
    reload_dirs = [
        str(base_dir / "api"),
        str(base_dir / "src"),
        str(base_dir / "config"),
    ]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=reload_dirs,
        reload_includes=["*.py"],
        reload_excludes=["*.pyc", "__pycache__", "*.pyo"]
    )
