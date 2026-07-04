from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.admin import routes as admin_routes
from app.api.routes import files_routes
from app.identity.schemas import UserResponse


def _admin_user() -> UserResponse:
    return UserResponse(
        uid="admin_1",
        email="admin@example.com",
        role="admin",
        isActive=True,
        createdAt=datetime.now(timezone.utc),
    )


def test_admin_invocations_paginates_with_total_count():
    rows = [
        {
            "usage_id": f"u{i}",
            "method": "GET",
            "path": f"/api/{i}",
            "feature": "chat_assistant" if i % 2 else "knowledge_management",
            "status_code": 200,
            "duration_ms": i,
            "user_id": "user_1",
            "model_id": "m1",
            "token_in": i,
            "token_out": i,
            "estimated_cost_usd": 0,
            "invoked_at": f"2026-01-01T00:00:0{i}+00:00",
        }
        for i in range(5)
    ]

    class Usage:
        def list_usage(self, **_: Any):
            return rows

    data = admin_routes.list_invocations(
        days=30,
        user_id=None,
        feature=None,
        model_id=None,
        method=None,
        status_family=None,
        path_query=None,
        query=None,
        skip=1,
        limit=2,
        sort_by="latency",
        sort_dir="asc",
        cache_bust=True,
        _admin=_admin_user(),
        usage_svc=Usage(),
    )
    assert data["count"] == 5
    assert [x["usage_id"] for x in data["items"]] == ["u1", "u2"]
    assert data["facets"]["features"] == ["chat_assistant", "knowledge_management"]


def test_admin_users_paginates_with_total_count():
    users = [
        UserResponse(uid=f"u{i}", email=f"u{i}@example.com", displayName=f"User {i}", role="student", isActive=True, createdAt=datetime(2026, 1, i + 1, tzinfo=timezone.utc))
        for i in range(4)
    ]

    class UserSvc:
        def list_users(self, **_: Any):
            return users

    data = admin_routes.list_users_admin(
        skip=1,
        limit=2,
        query=None,
        role=None,
        is_active=None,
        sort_by="email",
        sort_dir="asc",
        cache_bust=True,
        include_usage=False,
        usage_days=30,
        _admin=_admin_user(),
        user_service=UserSvc(),
        usage_svc=None,
    )
    assert data["count"] == 4
    assert [x["uid"] for x in data["items"]] == ["u1", "u2"]


def test_admin_knowledge_paginates_and_filters_tag():
    rows = [
        {"knowledge_id": "k1", "user_id": "u", "title": "A", "knowledge_type": "document", "status": "uploaded", "is_active": True, "tags": ["math"], "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
        {"knowledge_id": "k2", "user_id": "u", "title": "B", "knowledge_type": "document", "status": "uploaded", "is_active": True, "tags": ["math", "ml"], "created_at": "2026-01-02T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"},
        {"knowledge_id": "k3", "user_id": "u", "title": "C", "knowledge_type": "document", "status": "uploaded", "is_active": True, "tags": ["history"], "created_at": "2026-01-03T00:00:00Z", "updated_at": "2026-01-03T00:00:00Z"},
    ]

    class KnowledgeSvc:
        def list(self, **_: Any):
            return list(rows)

    data = admin_routes.list_knowledge_admin(
        query=None,
        user_id=None,
        knowledge_type=None,
        is_active=None,
        tag="math",
        skip=0,
        limit=1,
        sort_by="title",
        sort_dir="desc",
        cache_bust=True,
        sync_with_storage=False,
        include_usage=False,
        usage_days=30,
        _admin=_admin_user(),
        user_service=None,
        knowledge_svc=KnowledgeSvc(),
        usage_svc=None,
    )
    assert data["count"] == 2
    assert [x["knowledge_id"] for x in data["items"]] == ["k2"]


def test_files_with_metadata_paginates_and_returns_tags(monkeypatch: pytest.MonkeyPatch, tmp_path):
    f1 = tmp_path / "a.pdf"
    f2 = tmp_path / "b.pdf"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")
    (tmp_path / "a.pdf.metadata.json").write_text('{"knowledge_tags":["math","week1"]}', encoding="utf-8")

    class Storage:
        def list_input_files(self):
            return [
                {"name": "a.pdf", "path": str(f1), "size": "1 B", "modified": "2026-01-01T00:00:00Z", "type": ".pdf"},
                {"name": "b.pdf", "path": str(f2), "size": "1 B", "modified": "2026-01-02T00:00:00Z", "type": ".pdf"},
            ]

    monkeypatch.setattr(files_routes, "get_file_storage", lambda user_id: Storage())
    monkeypatch.setattr(files_routes, "build_processed_documents_snapshot", lambda *_, **__: {"documents": [], "stage_totals": {}, "document_count": 0})
    monkeypatch.setattr(files_routes, "_probe_live_index_sources_with_cache", lambda *_, **__: (set(), set()))

    data = files_routes.list_files_with_metadata(
        skip=0,
        limit=1,
        query=None,
        type=None,
        status=None,
        sort_by="name",
        sort_dir="asc",
        cache_bust=True,
        user_id="default",
    )
    assert data["count"] == 2
    assert len(data["files"]) == 1
    assert data["files"][0]["file_name"] == "a.pdf"
    assert data["files"][0]["tags"] == ["math", "week1"]
