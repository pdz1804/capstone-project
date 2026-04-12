from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import storage_user_id
from app.api.schemas import FeedbackCreateRequest, FeedbackItem, FeedbackListResponse
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def get_feedback_service() -> FeedbackService | None:
    try:
        return FeedbackService.from_env()
    except Exception:
        return None


@router.get("", response_model=FeedbackListResponse)
def list_feedback(
    limit: int = 30,
    cursor: str | None = None,
    category: str | None = None,
    session_id: str | None = None,
    user_id: str = Depends(storage_user_id),
    svc: FeedbackService | None = Depends(get_feedback_service),
):
    if svc is None:
        return FeedbackListResponse(items=[], next_cursor=None)

    items, next_cursor = svc.list_for_user(
        user_id=user_id,
        limit=limit,
        cursor=cursor,
        category=category,
        session_id=session_id,
        is_active=True,
    )
    return FeedbackListResponse(items=[FeedbackItem.model_validate(x) for x in items], next_cursor=next_cursor)


@router.get("/{feedback_id}", response_model=FeedbackItem)
def get_feedback(
    feedback_id: str,
    user_id: str = Depends(storage_user_id),
    svc: FeedbackService | None = Depends(get_feedback_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Feedback persistence is not configured.")
    item = svc.get_for_user(user_id=user_id, feedback_id=feedback_id)
    if not item or not bool(item.get("is_active", True)):
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return FeedbackItem.model_validate(item)


@router.post("", response_model=FeedbackItem)
def create_feedback(
    body: FeedbackCreateRequest,
    user_id: str = Depends(storage_user_id),
    svc: FeedbackService | None = Depends(get_feedback_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Feedback persistence is not configured.")

    try:
        vote = body.vote
        query = (body.query or "").strip()
        response = (body.response or "").strip()
        feedback_text = (body.feedback_text or "").strip()

        if vote in ("like", "dislike"):
            if not query:
                raise HTTPException(status_code=422, detail="query is required for like/dislike feedback.")
            if not response:
                raise HTTPException(status_code=422, detail="response is required for like/dislike feedback.")
        else:
            if not feedback_text:
                raise HTTPException(status_code=422, detail="feedback_text is required for general feedback.")
            if not query:
                query = feedback_text

        item = svc.create_for_user(
            user_id=user_id,
            vote=vote,
            query=query,
            response=response,
            session_id=body.session_id,
            message_id=body.message_id,
            reason_code=body.reason_code,
            reason_text=body.reason_text,
            scope=(body.scope or "").strip() or None,
            feedback_text=feedback_text or None,
        )
        # Non-blocking analysis path: return immediately, classify in worker thread.
        svc.schedule_analysis(user_id=user_id, feedback_id=str(item.get("feedback_id") or ""))
        return FeedbackItem.model_validate(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_feedback failed")
        raise HTTPException(status_code=500, detail=f"Could not create feedback: {e}") from e
