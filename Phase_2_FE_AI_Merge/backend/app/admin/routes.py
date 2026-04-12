from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from app.identity.routes import get_current_admin, get_user_service
from app.identity.schemas import UserResponse, UserUpdate
from app.identity.user_service import UserService
from app.services.app_usage_service import AppUsageService, MODEL_PRICES
from app.services.feedback_service import FeedbackService
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/admin", tags=["admin"])
_KNOWLEDGE_SERVICE_SINGLETON: KnowledgeService | None = None


def get_usage_service() -> AppUsageService | None:
    return AppUsageService.from_env_optional()


def get_feedback_service() -> FeedbackService | None:
    try:
        return FeedbackService.from_env()
    except Exception:
        return None


def get_knowledge_service() -> KnowledgeService | None:
    global _KNOWLEDGE_SERVICE_SINGLETON
    if _KNOWLEDGE_SERVICE_SINGLETON is None:
        _KNOWLEDGE_SERVICE_SINGLETON = KnowledgeService.from_env_optional()
    return _KNOWLEDGE_SERVICE_SINGLETON


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    username: Optional[str] = None
    displayName: Optional[str] = None
    role: str = "student"


class AdminUserUpdateRequest(BaseModel):
    username: Optional[str] = None
    displayName: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None
    photoURL: Optional[str] = None
    persona: Optional[str] = None
    educationDescription: Optional[str] = None


class AdminKnowledgeCreateRequest(BaseModel):
    user_id: str
    title: str
    source_path: Optional[str] = None
    knowledge_type: Optional[str] = None
    status: Optional[str] = "uploaded"
    is_active: bool = True
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = ""


class AdminKnowledgeUpdateRequest(BaseModel):
    title: Optional[str] = None
    source_path: Optional[str] = None
    knowledge_type: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class AdminFeedbackCreateRequest(BaseModel):
    user_id: str
    vote: Literal["like", "dislike", "general"]
    query: Optional[str] = None
    response: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    scope: Optional[str] = None
    feedback_text: Optional[str] = None


class AdminFeedbackUpdateRequest(BaseModel):
    category: Optional[str] = None
    sub_category: Optional[str] = None
    suggested_action: Optional[str] = None
    analysis_summary: Optional[str] = None
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    scope: Optional[str] = None
    feedback_text: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/dashboard")
def get_admin_dashboard(
    days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if usage_svc is None:
        return {
            "days": days,
            "summary": {
                "total_requests": 0,
                "unique_users": 0,
                "token_in": 0,
                "token_out": 0,
                "estimated_cost_usd": 0.0,
                "avg_duration_ms": 0,
                "error_requests": 0,
                "error_rate_percent": 0.0,
            },
            "feedback_coverage": {
                "chat_requests": 0,
                "feedback_requests": 0,
                "coverage_ratio": 0.0,
                "coverage_percent": 0.0,
            },
            "requests_by_feature": [],
            "requests_by_day": [],
            "requests_by_hour": [],
            "active_users_by_day": [],
            "active_users_by_hour": [],
            "tokens_by_day": [],
            "tokens_by_hour": [],
            "requests_by_status": [],
            "requests_by_user": [],
            "model_usage": [],
            "pricing_catalog": [
                {
                    "model_id": p.model_id,
                    "display_name": p.display_name,
                    "input_price_per_million": p.input_price_per_million,
                    "output_price_per_million": p.output_price_per_million,
                }
                for p in MODEL_PRICES
            ],
        }
    return usage_svc.dashboard_summary(days=days)


@router.get("/invocations")
def list_invocations(
    days: int = Query(30, ge=1, le=365),
    user_id: str | None = Query(None),
    feature: str | None = Query(None),
    model_id: str | None = Query(None),
    limit: int = Query(300, ge=1, le=5000),
    _admin: UserResponse = Depends(get_current_admin),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if usage_svc is None:
        return {"items": [], "count": 0}
    rows = usage_svc.list_usage(days=days, user_id=user_id, feature=feature, model_id=model_id, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.get("/users")
def list_users_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    query: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    include_usage: bool = Query(False),
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    rows = user_service.list_users(skip=skip, limit=limit, query=query, role=role, is_active=is_active)
    items: List[Dict[str, Any]] = []
    for row in rows:
        obj = row.model_dump()
        if include_usage and usage_svc is not None:
            obj["usage_summary"] = usage_svc.user_usage_summary(row.uid, days=usage_days)
        items.append(obj)
    return {"items": items, "count": len(items)}


@router.post("/users", response_model=UserResponse)
def create_user_admin(
    body: AdminUserCreateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
):
    return user_service.create_user_by_admin(
        email=str(body.email),
        password=body.password,
        display_name=body.displayName,
        role=body.role,
        username=body.username,
    )


@router.get("/users/{uid}")
def get_user_admin_detail(
    uid: str,
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    user = user_service.user_repo.get_by_id(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    out = user.model_dump()
    if usage_svc is not None:
        out["usage_summary"] = usage_svc.user_usage_summary(uid, days=usage_days)
    return out


@router.patch("/users/{uid}", response_model=UserResponse)
def update_user_admin(
    uid: str,
    body: AdminUserUpdateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
):
    updated = user_service.update_user_profile(uid, UserUpdate(**body.model_dump(exclude_unset=True)))
    return updated


@router.post("/users/{uid}/deactivate", response_model=UserResponse)
def deactivate_user_admin(
    uid: str,
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
):
    return user_service.set_user_active(uid, False)


@router.post("/users/{uid}/activate", response_model=UserResponse)
def activate_user_admin(
    uid: str,
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
):
    return user_service.set_user_active(uid, True)


@router.delete("/users/{uid}")
def delete_user_admin(
    uid: str,
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
):
    deleted = user_service.delete_user(uid)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True, "uid": uid}


@router.get("/users/{uid}/usage-summary")
def user_usage_summary_admin(
    uid: str,
    days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if usage_svc is None:
        return {
            "user_id": uid,
            "days": days,
            "total_requests": 0,
            "token_in": 0,
            "token_out": 0,
            "estimated_cost_usd": 0.0,
            "requests_by_feature": [],
        }
    return usage_svc.user_usage_summary(uid, days=days)


@router.post("/knowledge/sync")
def sync_knowledge_admin(
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")

    users = user_service.list_users(skip=0, limit=5000)
    synced = knowledge_svc.sync_input_files_for_users([u.uid for u in users])
    return {"synced": synced, "users": len(users)}


@router.get("/knowledge")
def list_knowledge_admin(
    query: str | None = Query(None),
    user_id: str | None = Query(None),
    knowledge_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    sync_with_storage: bool = Query(False),
    include_usage: bool = Query(False),
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if knowledge_svc is None:
        return {"items": [], "count": 0}

    if sync_with_storage:
        users = user_service.list_users(skip=0, limit=5000)
        knowledge_svc.sync_input_files_for_users([u.uid for u in users])

    known_user_ids = [user_id] if user_id else None

    rows = knowledge_svc.list(
        user_id=user_id,
        known_user_ids=known_user_ids,
        knowledge_type=knowledge_type,
        is_active=is_active,
        query=query,
        limit=limit,
    )
    if include_usage and usage_svc is not None:
        for row in rows:
            row["usage_summary"] = usage_svc.user_usage_summary(str(row.get("user_id") or ""), days=usage_days)

    return {"items": rows, "count": len(rows)}


@router.post("/knowledge")
def create_knowledge_admin(
    body: AdminKnowledgeCreateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    try:
        item = knowledge_svc.create(body.model_dump())
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/knowledge/{knowledge_id}")
def get_knowledge_admin(
    knowledge_id: str,
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    item = knowledge_svc.get(knowledge_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    if usage_svc is not None:
        item["usage_summary"] = usage_svc.user_usage_summary(str(item.get("user_id") or ""), days=usage_days)
    return item


@router.patch("/knowledge/{knowledge_id}")
def update_knowledge_admin(
    knowledge_id: str,
    body: AdminKnowledgeUpdateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    item = knowledge_svc.update(knowledge_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return item


@router.post("/knowledge/{knowledge_id}/deactivate")
def deactivate_knowledge_admin(
    knowledge_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    item = knowledge_svc.update(knowledge_id, {"is_active": False})
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return item


@router.post("/knowledge/{knowledge_id}/activate")
def activate_knowledge_admin(
    knowledge_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    item = knowledge_svc.update(knowledge_id, {"is_active": True})
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return item


@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge_admin(
    knowledge_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
):
    if knowledge_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Knowledge persistence is not configured")
    result = knowledge_svc.delete_with_report(knowledge_id)
    if not bool(result.get("deleted")):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return result


@router.get("/feedback")
def list_feedback_admin(
    limit: int = Query(500, ge=1, le=5000),
    user_id: str | None = Query(None),
    category: str | None = Query(None),
    vote: str | None = Query(None),
    is_active: bool | None = Query(None),
    query: str | None = Query(None),
    include_usage: bool = Query(False),
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if feedback_svc is None:
        return {"items": [], "count": 0}

    items = feedback_svc.list_all(
        limit=limit,
        user_id=user_id,
        category=category,
        vote=vote,
        is_active=is_active,
        query=query,
    )

    if include_usage and usage_svc is not None:
        for item in items:
            item["usage_summary"] = usage_svc.user_usage_summary(str(item.get("user_id") or ""), days=usage_days)

    return {"items": items, "count": len(items)}


@router.post("/feedback")
def create_feedback_admin(
    body: AdminFeedbackCreateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    item = feedback_svc.create_for_user(
        user_id=body.user_id,
        vote=body.vote,
        query=(body.query or "").strip(),
        response=(body.response or "").strip(),
        session_id=body.session_id,
        message_id=body.message_id,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        scope=body.scope,
        feedback_text=body.feedback_text,
    )
    feedback_svc.schedule_analysis(user_id=body.user_id, feedback_id=str(item.get("feedback_id") or ""))
    return item


@router.get("/feedback/{user_id}/{feedback_id}")
def get_feedback_admin_detail(
    user_id: str,
    feedback_id: str,
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    item = feedback_svc.get_for_user(user_id=user_id, feedback_id=feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if usage_svc is not None:
        item["usage_summary"] = usage_svc.user_usage_summary(user_id, days=usage_days)
    return item


@router.patch("/feedback/{user_id}/{feedback_id}")
def update_feedback_admin(
    user_id: str,
    feedback_id: str,
    body: AdminFeedbackUpdateRequest,
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    item = feedback_svc.update_feedback_admin(
        user_id=user_id,
        feedback_id=feedback_id,
        data=body.model_dump(exclude_unset=True),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return item


@router.post("/feedback/{user_id}/{feedback_id}/deactivate")
def deactivate_feedback_admin(
    user_id: str,
    feedback_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    item = feedback_svc.update_feedback_admin(user_id=user_id, feedback_id=feedback_id, data={"is_active": False})
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return item


@router.post("/feedback/{user_id}/{feedback_id}/activate")
def activate_feedback_admin(
    user_id: str,
    feedback_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    item = feedback_svc.update_feedback_admin(user_id=user_id, feedback_id=feedback_id, data={"is_active": True})
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return item


@router.delete("/feedback/{user_id}/{feedback_id}")
def delete_feedback_admin(
    user_id: str,
    feedback_id: str,
    _admin: UserResponse = Depends(get_current_admin),
    feedback_svc: FeedbackService | None = Depends(get_feedback_service),
):
    if feedback_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback persistence is not configured")

    deleted = feedback_svc.delete_feedback(user_id=user_id, feedback_id=feedback_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"deleted": True, "user_id": user_id, "feedback_id": feedback_id}
