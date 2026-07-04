from __future__ import annotations

import threading
import time
import os
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from app.identity.routes import get_current_admin, get_user_service
from app.identity.schemas import UserResponse, UserUpdate
from app.identity.user_service import UserService
from app.services.app_usage_service import AppUsageService, MODEL_PRICES
from app.services.cost_report_service import CostReportService
from app.services.feedback_service import FeedbackService
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/admin", tags=["admin"])
_KNOWLEDGE_SERVICE_SINGLETON: KnowledgeService | None = None
_KNOWLEDGE_SERVICE_LOCK = threading.Lock()
_ADMIN_LIST_CACHE: Dict[str, tuple[float, Any]] = {}
_ADMIN_LIST_CACHE_LOCK = threading.Lock()
_ADMIN_LIST_CACHE_TTL_SECONDS = max(1, int(float(os.getenv("ADMIN_LIST_CACHE_TTL_SECONDS", "45") or "45")))


def _cache_get(key: str) -> Any | None:
    now = time.time()
    with _ADMIN_LIST_CACHE_LOCK:
        item = _ADMIN_LIST_CACHE.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at <= now:
            _ADMIN_LIST_CACHE.pop(key, None)
            return None
        return payload


def _cache_set(key: str, payload: Any) -> None:
    with _ADMIN_LIST_CACHE_LOCK:
        _ADMIN_LIST_CACHE[key] = (time.time() + _ADMIN_LIST_CACHE_TTL_SECONDS, payload)


def _sort_dir(value: str | None) -> str:
    return "asc" if str(value or "").lower() == "asc" else "desc"


def _slice_page(rows: List[Dict[str, Any]], skip: int, limit: int | None) -> List[Dict[str, Any]]:
    skip_n = max(0, int(skip or 0))
    if limit is None:
        return rows[skip_n:]
    limit_n = max(1, int(limit))
    return rows[skip_n : skip_n + limit_n]


def _sort_dict_rows(rows: List[Dict[str, Any]], sort_by: str, sort_dir: str, key_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    key_fn = key_map.get(sort_by) or key_map.get("default")
    reverse = _sort_dir(sort_dir) == "desc"
    return sorted(rows, key=key_fn, reverse=reverse)


def get_usage_service() -> AppUsageService | None:
    return AppUsageService.from_env_optional()


def get_feedback_service() -> FeedbackService | None:
    try:
        return FeedbackService.from_env()
    except Exception:
        return None


def get_cost_report_service() -> CostReportService | None:
    try:
        return CostReportService.from_env_optional()
    except Exception:
        return None


def get_knowledge_service() -> KnowledgeService | None:
    """Thread-safe singleton getter for KnowledgeService using double-checked locking."""
    global _KNOWLEDGE_SERVICE_SINGLETON
    # First check without lock (fast path)
    if _KNOWLEDGE_SERVICE_SINGLETON is not None:
        return _KNOWLEDGE_SERVICE_SINGLETON

    # Second check with lock (slow path)
    with _KNOWLEDGE_SERVICE_LOCK:
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
    method: str | None = Query(None),
    status_family: str | None = Query(None),
    path_query: str | None = Query(None),
    query: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=50000),
    sort_by: str = Query("time"),
    sort_dir: str = Query("desc"),
    cache_bust: bool = Query(False),
    _admin: UserResponse = Depends(get_current_admin),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if usage_svc is None:
        return {"items": [], "count": 0, "skip": skip, "limit": limit, "facets": {"features": [], "models": []}}

    method_q = (method or "").strip().upper()
    status_q = (status_family or "").strip().lower()
    path_q = (path_query or "").strip().lower()
    q = (query or "").strip().lower()
    cache_key = "|".join(
        [
            "invocations",
            str(days),
            user_id or "",
            feature or "",
            model_id or "",
            method_q,
            status_q,
            path_q,
            q,
        ]
    )
    rows = None if cache_bust else _cache_get(cache_key)
    if rows is None:
        rows = usage_svc.list_usage(days=days, user_id=user_id, feature=feature, model_id=model_id, limit=None)
        if method_q:
            rows = [x for x in rows if str(x.get("method") or "").upper() == method_q]
        if status_q == "2xx":
            rows = [x for x in rows if 200 <= int(x.get("status_code") or 0) < 300]
        elif status_q == "4xx":
            rows = [x for x in rows if 400 <= int(x.get("status_code") or 0) < 500]
        elif status_q == "5xx":
            rows = [x for x in rows if 500 <= int(x.get("status_code") or 0) < 600]
        if path_q:
            rows = [x for x in rows if path_q in str(x.get("path") or "").lower()]
        if q:
            rows = [
                x
                for x in rows
                if q
                in " ".join(
                    [
                        str(x.get("usage_id") or ""),
                        str(x.get("user_id") or ""),
                        str(x.get("feature") or ""),
                        str(x.get("path") or ""),
                        str(x.get("model_id") or ""),
                        str(x.get("method") or ""),
                        str(x.get("status_code") or ""),
                    ]
                ).lower()
            ]
        _cache_set(cache_key, rows)

    key_map = {
        "time": lambda x: str(x.get("invoked_at") or ""),
        "methodPath": lambda x: f"{str(x.get('method') or '').upper()} {str(x.get('path') or '').lower()}",
        "feature": lambda x: str(x.get("feature") or "").lower(),
        "user": lambda x: str(x.get("user_id") or "").lower(),
        "model": lambda x: str(x.get("model_id") or "").lower(),
        "status": lambda x: int(x.get("status_code") or 0),
        "latency": lambda x: int(x.get("duration_ms") or 0),
        "in": lambda x: int(x.get("token_in") or 0),
        "out": lambda x: int(x.get("token_out") or 0),
        "cost": lambda x: float(x.get("estimated_cost_usd") or 0.0),
        "default": lambda x: str(x.get("invoked_at") or ""),
    }
    sorted_rows = _sort_dict_rows(list(rows), sort_by, sort_dir, key_map)
    facets = {
        "features": sorted({str(x.get("feature") or "") for x in rows if str(x.get("feature") or "")})[:500],
        "models": sorted({str(x.get("model_id") or "") for x in rows if str(x.get("model_id") or "")})[:500],
    }
    return {
        "items": _slice_page(sorted_rows, skip, limit),
        "count": len(rows),
        "skip": skip,
        "limit": limit,
        "facets": facets,
    }


@router.get("/costs")
def get_admin_costs(
    days: int = Query(30, ge=1, le=365),
    service: str | None = Query(None),
    _admin: UserResponse = Depends(get_current_admin),
    cost_svc: CostReportService | None = Depends(get_cost_report_service),
):
    if cost_svc is None:
        return CostReportService.empty_dashboard(days=days)
    try:
        return cost_svc.dashboard_summary(days=days, service_filter=service)
    except Exception as e:
        return CostReportService.empty_dashboard(
            days=days,
            bucket=cost_svc.bucket,
            prefix=cost_svc.prefix,
            error=str(e),
        )


@router.get("/users")
def list_users_admin(
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=50000),
    query: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("user"),
    sort_dir: str = Query("asc"),
    cache_bust: bool = Query(False),
    include_usage: bool = Query(False),
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    cache_key = "|".join(["users", query or "", role or "", str(is_active), str(include_usage), str(usage_days)])
    rows = None if cache_bust else _cache_get(cache_key)
    if rows is None:
        rows = [x.model_dump() for x in user_service.list_users(skip=0, limit=None, query=query, role=role, is_active=is_active)]
        _cache_set(cache_key, rows)

    key_map = {
        "user": lambda x: str(x.get("displayName") or x.get("username") or x.get("email") or x.get("uid") or "").lower(),
        "email": lambda x: str(x.get("email") or "").lower(),
        "role": lambda x: str(x.get("role") or "").lower(),
        "status": lambda x: int(bool(x.get("isActive", True))),
        "created": lambda x: str(x.get("createdAt") or ""),
        "default": lambda x: str(x.get("displayName") or x.get("username") or x.get("email") or x.get("uid") or "").lower(),
    }
    sorted_rows = _sort_dict_rows(list(rows), sort_by, sort_dir, key_map)
    page_rows = _slice_page(sorted_rows, skip, limit)
    items: List[Dict[str, Any]] = []
    for obj in page_rows:
        obj = dict(obj)
        if include_usage and usage_svc is not None:
            obj["usage_summary"] = usage_svc.user_usage_summary(str(obj.get("uid") or ""), days=usage_days)
        items.append(obj)
    return {"items": items, "count": len(rows), "skip": skip, "limit": limit}


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

    users = user_service.list_users(skip=0, limit=None)
    synced = knowledge_svc.sync_input_files_for_users([u.uid for u in users])
    return {"synced": synced, "users": len(users)}


@router.get("/knowledge")
def list_knowledge_admin(
    query: str | None = Query(None),
    user_id: str | None = Query(None),
    knowledge_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    tag: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=50000),
    sort_by: str = Query("uploaded"),
    sort_dir: str = Query("desc"),
    cache_bust: bool = Query(False),
    sync_with_storage: bool = Query(False),
    include_usage: bool = Query(False),
    usage_days: int = Query(30, ge=1, le=365),
    _admin: UserResponse = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
    knowledge_svc: KnowledgeService | None = Depends(get_knowledge_service),
    usage_svc: AppUsageService | None = Depends(get_usage_service),
):
    if knowledge_svc is None:
        return {"items": [], "count": 0, "skip": skip, "limit": limit}

    if sync_with_storage:
        users = user_service.list_users(skip=0, limit=None)
        knowledge_svc.sync_input_files_for_users([u.uid for u in users])

    known_user_ids = [user_id] if user_id else None

    cache_key = "|".join(["knowledge", query or "", user_id or "", knowledge_type or "", str(is_active), tag or ""])
    rows = None if cache_bust else _cache_get(cache_key)
    if rows is None:
        rows = knowledge_svc.list(
            user_id=user_id,
            known_user_ids=known_user_ids,
            knowledge_type=knowledge_type,
            is_active=is_active,
            query=query,
            limit=None,
        )
        tag_q = (tag or "").strip().lower()
        if tag_q:
            rows = [
                x
                for x in rows
                if any(tag_q in str(t or "").strip().lower() for t in (x.get("tags") or []))
            ]
        _cache_set(cache_key, rows)

    key_map = {
        "title": lambda x: str(x.get("title") or "").lower(),
        "uploaded": lambda x: str(x.get("created_at") or x.get("updated_at") or ""),
        "updated": lambda x: str(x.get("updated_at") or x.get("created_at") or ""),
        "user": lambda x: str(x.get("user_id") or "").lower(),
        "type": lambda x: str(x.get("knowledge_type") or "").lower(),
        "status": lambda x: f"{int(bool(x.get('is_active', True)))}-{str(x.get('status') or '').lower()}",
        "default": lambda x: str(x.get("created_at") or x.get("updated_at") or ""),
    }
    sorted_rows = _sort_dict_rows(list(rows), sort_by, sort_dir, key_map)
    page_rows = _slice_page(sorted_rows, skip, limit)
    if include_usage and usage_svc is not None:
        for row in page_rows:
            row["usage_summary"] = usage_svc.user_usage_summary(str(row.get("user_id") or ""), days=usage_days)

    return {"items": page_rows, "count": len(rows), "skip": skip, "limit": limit}


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
    limit: int | None = Query(None, ge=1, le=50000),
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
