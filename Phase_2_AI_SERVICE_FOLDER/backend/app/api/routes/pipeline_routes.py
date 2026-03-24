import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.paths import OUTPUT_DIR, merged_runtime_settings
from app.services.indexing_service import IndexingService
from app.services.processing_service import run_processing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])


@router.get("/processing-stats")
async def processing_stats() -> Dict[str, Any]:
    p = OUTPUT_DIR / "processing" / "pipeline_stats.json"
    if not p.exists():
        return {"error": "No processing stats found"}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


@router.post("/process")
async def process(force: bool = False) -> Dict[str, Any]:
    try:
        stats = run_processing(force=force)
        if isinstance(stats, dict) and stats.get("status") == "failed":
            raise HTTPException(status_code=500, detail=stats.get("error", "Processing failed"))
        return {"status": "completed", "results": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("process")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/index")
async def index_all(force: bool = False) -> Dict[str, Any]:
    try:
        cfg = merged_runtime_settings()
        svc = IndexingService(cfg)
        out = svc.index_all(force=force)
        if out.get("text", {}).get("status") == "failed":
            raise HTTPException(status_code=500, detail=out["text"].get("error"))
        if out.get("image", {}).get("status") == "failed":
            raise HTTPException(status_code=500, detail=out["image"].get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("index")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/index/text")
async def index_text(force: bool = False) -> Dict[str, Any]:
    try:
        cfg = merged_runtime_settings()
        out = IndexingService(cfg).index_text(force=force)
        if out.get("status") == "failed":
            raise HTTPException(status_code=500, detail=out.get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/index/image")
async def index_image(force: bool = False) -> Dict[str, Any]:
    try:
        cfg = merged_runtime_settings()
        out = IndexingService(cfg).index_images(force=force)
        if out.get("status") == "failed":
            raise HTTPException(status_code=500, detail=out.get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
