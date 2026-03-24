import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import McqRequest, RoadmapRequest, SummaryRequest
from app.core.paths import merged_runtime_settings
from app.services.insights_service import InsightsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/summary")
async def lecture_summary(req: SummaryRequest):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg).lecture_summary(
            focus_query=req.focus_query,
            depth=req.depth,
            top_k=req.top_k,
        )
    except Exception as e:
        logger.exception("summary")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/mcq")
async def mcq(req: McqRequest):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg).mcq_quiz(req.topic, req.num_questions, req.difficulty)
    except Exception as e:
        logger.exception("mcq")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/learning-roadmap")
async def roadmap(req: RoadmapRequest):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg).learning_roadmap(req.student_profile, req.goals)
    except Exception as e:
        logger.exception("roadmap")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analytics")
async def analytics():
    cfg = merged_runtime_settings()
    return InsightsService(cfg).analytics_placeholder()
