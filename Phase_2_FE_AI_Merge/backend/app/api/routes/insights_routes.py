import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import storage_user_id
from app.api.schemas import McqRequest, RoadmapRequest, SummaryRequest
from app.core.paths import merged_runtime_settings
from app.services.insights_service import InsightsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/summary")
def lecture_summary(
    req: SummaryRequest,
    user_id: str = Depends(storage_user_id),
):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg, user_id=user_id).lecture_summary(
            focus_query=req.focus_query,
            depth=req.depth,
            top_k=req.top_k,
            document_id=req.document_id,
            tone=req.tone,
            target_length=req.target_length,
        )
    except Exception as e:
        logger.exception("summary")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/mcq")
def mcq(
    req: McqRequest,
    user_id: str = Depends(storage_user_id),
):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg, user_id=user_id).mcq_quiz(
            req.topic,
            req.num_questions,
            req.difficulty,
            document_id=req.document_id,
            question_style=req.question_style,
            include_explanations=req.include_explanations,
        )
    except Exception as e:
        logger.exception("mcq")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/learning-roadmap")
def roadmap(
    req: RoadmapRequest,
    user_id: str = Depends(storage_user_id),
):
    try:
        cfg = merged_runtime_settings()
        return InsightsService(cfg, user_id=user_id).learning_roadmap(
            req.student_profile,
            req.goals,
            document_id=req.document_id,
        )
    except Exception as e:
        logger.exception("roadmap")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analytics")
def analytics(user_id: str = Depends(storage_user_id)):
    cfg = merged_runtime_settings()
    return InsightsService(cfg, user_id=user_id).analytics_placeholder()
