from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import storage_user_id
from app.api.schemas import QuizResultCreateRequest, QuizResultsListResponse
from app.services.quiz_results_service import QuizResultsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["quiz-results"])


def get_quiz_results_service() -> QuizResultsService | None:
    try:
        return QuizResultsService.from_env()
    except RuntimeError:
        return None


@router.get("/quiz-results", response_model=QuizResultsListResponse)
async def list_quiz_results(
    limit: int = Query(200, ge=1, le=1000),
    user_id: str = Depends(storage_user_id),
    svc: QuizResultsService | None = Depends(get_quiz_results_service),
):
    if svc is None:
        # Keep app usable even before table is provisioned.
        return {"items": []}
    try:
        return {"items": svc.list_for_user(user_id=user_id, limit=limit)}
    except Exception as e:
        logger.exception("list quiz results failed")
        raise HTTPException(status_code=500, detail=f"Could not list quiz results: {e}") from e


@router.post("/quiz-results")
async def create_quiz_result(
    body: QuizResultCreateRequest,
    user_id: str = Depends(storage_user_id),
    svc: QuizResultsService | None = Depends(get_quiz_results_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Quiz result persistence is not configured.")
    try:
        item = svc.create_for_user(
            user_id=user_id,
            score=body.score,
            total=body.total,
            file_id=body.file_id,
            document_id=body.document_id,
            quiz_topic=body.quiz_topic,
        )
        return {"item": item}
    except Exception as e:
        logger.exception("create quiz result failed")
        raise HTTPException(status_code=500, detail=f"Could not store quiz result: {e}") from e

