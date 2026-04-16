import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

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
        result = InsightsService(cfg, user_id=user_id).lecture_summary(
            focus_query=req.focus_query,
            depth=req.depth,
            top_k=req.top_k,
            document_id=req.document_id,
            tone=req.tone,
            target_length=req.target_length,
        )
        usage = (result.get("usage") or {}) if isinstance(result, dict) else {}
        return JSONResponse(
            content=result,
            headers={
                "X-Usage-Feature": "learning_insights",
                "X-Usage-Model-Id": str(usage.get("model_id") or ""),
                "X-Usage-Token-In": str(int(usage.get("token_in") or 0)),
                "X-Usage-Token-Out": str(int(usage.get("token_out") or 0)),
            },
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
        result = InsightsService(cfg, user_id=user_id).mcq_quiz(
            req.topic,
            req.num_questions,
            req.difficulty,
            document_id=req.document_id,
            question_style=req.question_style,
            include_explanations=req.include_explanations,
        )
        usage = (result.get("usage") or {}) if isinstance(result, dict) else {}
        return JSONResponse(
            content=result,
            headers={
                "X-Usage-Feature": "learning_insights",
                "X-Usage-Model-Id": str(usage.get("model_id") or ""),
                "X-Usage-Token-In": str(int(usage.get("token_in") or 0)),
                "X-Usage-Token-Out": str(int(usage.get("token_out") or 0)),
            },
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
        result = InsightsService(cfg, user_id=user_id).learning_roadmap(
            req.student_profile,
            req.goals,
            document_id=req.document_id,
        )
        usage = (result.get("usage") or {}) if isinstance(result, dict) else {}
        return JSONResponse(
            content=result,
            headers={
                "X-Usage-Feature": "learning_insights",
                "X-Usage-Model-Id": str(usage.get("model_id") or ""),
                "X-Usage-Token-In": str(int(usage.get("token_in") or 0)),
                "X-Usage-Token-Out": str(int(usage.get("token_out") or 0)),
            },
        )
    except Exception as e:
        logger.exception("roadmap")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analytics")
def analytics(user_id: str = Depends(storage_user_id)):
    cfg = merged_runtime_settings()
    return InsightsService(cfg, user_id=user_id).analytics_placeholder()
