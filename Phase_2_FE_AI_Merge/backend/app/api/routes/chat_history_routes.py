from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import storage_user_id
from app.api.schemas import (
    ChatMessageItem,
    ChatMessagesListResponse,
    ChatSessionCreateRequest,
    ChatSessionItem,
    ChatSessionsListResponse,
    ChatSessionUpdateRequest,
)
from app.services.chat_attachment_storage import read_chat_attachment_bytes
from app.services.chat_history_service import ChatHistoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat-history"])


def get_chat_history_service() -> ChatHistoryService | None:
    try:
        return ChatHistoryService.from_env()
    except Exception:
        return None


@router.get("/sessions", response_model=ChatSessionsListResponse)
def list_chat_sessions(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    logger.info("list_chat_sessions: user_id=%s limit=%d", user_id, limit)
    if svc is None:
        logger.warning("list_chat_sessions: ChatHistoryService is None")
        return ChatSessionsListResponse(items=[], next_cursor=None)
    try:
        items, next_cursor = svc.list_sessions(user_id=user_id, limit=limit, cursor=cursor)
        logger.info("list_chat_sessions: Retrieved %d sessions for user_id=%s", len(items), user_id)
        return ChatSessionsListResponse(
            items=[ChatSessionItem.model_validate(x) for x in items],
            next_cursor=next_cursor,
        )
    except Exception as e:
        logger.warning("list_chat_sessions failed for user_id=%s: %s", user_id, e)
        return ChatSessionsListResponse(items=[], next_cursor=None)


@router.post("/sessions")
def create_chat_session(
    body: ChatSessionCreateRequest,
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Chat history persistence is not configured.")

    session_id = (body.session_id or "").strip() or str(uuid.uuid4())
    try:
        item = svc.ensure_session(
            user_id=user_id,
            session_id=session_id,
            title=body.title,
            pinned=body.pinned,
        )
        return {"item": ChatSessionItem.model_validate(item)}
    except Exception as e:
        logger.exception("create_chat_session failed")
        raise HTTPException(status_code=500, detail=f"Could not create chat session: {e}") from e


@router.patch("/sessions/{session_id}")
def update_chat_session(
    session_id: str,
    body: ChatSessionUpdateRequest,
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Chat history persistence is not configured.")

    try:
        item = svc.update_session(
            user_id=user_id,
            session_id=session_id,
            title=body.title,
            pinned=body.pinned,
        )
        if not item:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        return {"item": ChatSessionItem.model_validate(item)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_chat_session failed")
        raise HTTPException(status_code=500, detail=f"Could not update chat session: {e}") from e


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesListResponse)
def list_chat_session_messages(
    session_id: str,
    limit: int = Query(60, ge=1, le=200),
    cursor: str | None = Query(None),
    newest_first: bool = Query(False),
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    if svc is None:
        return ChatMessagesListResponse(items=[], next_cursor=None)

    try:
        session = svc.get_session(user_id=user_id, session_id=session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")

        items, next_cursor = svc.list_messages(
            user_id=user_id,
            session_id=session_id,
            limit=limit,
            cursor=cursor,
            newest_first=newest_first,
        )
        return ChatMessagesListResponse(
            items=[ChatMessageItem.model_validate(x) for x in items],
            next_cursor=next_cursor,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("list_chat_session_messages failed")
        raise HTTPException(status_code=500, detail=f"Could not list chat messages: {e}") from e


@router.get("/attachment")
def get_chat_attachment(
    session_id: str = Query(..., min_length=8),
    message_id: str = Query(..., min_length=4),
    index: int = Query(0, ge=0, le=32),
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    """Return a persisted chat infographic (binary). Same auth as chat history."""
    if svc is None:
        raise HTTPException(status_code=503, detail="Chat history persistence is not configured.")
    msg = svc.get_message(user_id=user_id, session_id=session_id, message_id=message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
    atts = msg.get("attachments") or []
    if not isinstance(atts, list) or index >= len(atts):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    att = atts[index]
    if not isinstance(att, dict) or str(att.get("type") or "") != "image":
        raise HTTPException(status_code=404, detail="Attachment not found.")
    rel_path = str(att.get("rel_path") or "").strip()
    mime = str(att.get("mime") or "image/png").split(";")[0].strip() or "image/png"
    if not rel_path:
        raise HTTPException(status_code=404, detail="Attachment path missing.")
    out = read_chat_attachment_bytes(user_id, rel_path)
    if not out:
        raise HTTPException(status_code=404, detail="Attachment file missing.")
    body, _fallback_ct = out
    return Response(content=body, media_type=mime)


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    user_id: str = Depends(storage_user_id),
    svc: ChatHistoryService | None = Depends(get_chat_history_service),
):
    if svc is None:
        raise HTTPException(status_code=503, detail="Chat history persistence is not configured.")

    try:
        deleted = svc.delete_session(user_id=user_id, session_id=session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        return {"deleted": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("delete_chat_session failed")
        raise HTTPException(status_code=500, detail=f"Could not delete chat session: {e}") from e
