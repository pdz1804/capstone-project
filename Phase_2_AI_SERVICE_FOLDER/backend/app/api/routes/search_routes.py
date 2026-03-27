import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import storage_user_id
from app.api.schemas import SearchRequest
from app.core.paths import merged_runtime_settings
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
async def search(
    req: SearchRequest,
    user_id: str = Depends(storage_user_id),
):
    try:
        cfg = merged_runtime_settings()
        orch = SearchOrchestrator(cfg, user_id=user_id)
        return orch.run(
            query=req.query,
            top_k=req.top_k,
            retriever_type=req.retriever_type,
            include_images=req.include_images,
            images_for_generation=req.images_for_generation,
        )
    except Exception as e:
        logger.exception("search")
        raise HTTPException(status_code=500, detail=str(e)) from e
