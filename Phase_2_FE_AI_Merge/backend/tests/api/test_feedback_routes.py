from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes.feedback_routes import get_feedback_service


class _FakeFeedbackService:
    def __init__(self):
        self.items = []
        self.scheduled = []

    def list_for_user(self, *, user_id, limit=30, cursor=None, category=None, session_id=None, is_active=True):
        rows = [x for x in self.items if x.get("user_id") == user_id]
        if category:
            rows = [x for x in rows if (x.get("category") or "").lower() == str(category).lower()]
        if session_id:
            rows = [x for x in rows if (x.get("session_id") or "") == session_id]
        if is_active is not None:
            rows = [x for x in rows if bool(x.get("is_active", True)) == bool(is_active)]
        return rows[:limit], None

    def get_for_user(self, *, user_id, feedback_id):
        for x in self.items:
            if x.get("user_id") == user_id and x.get("feedback_id") == feedback_id:
                return x
        return None

    def create_for_user(self, **kwargs):
        item = {
            "user_id": kwargs["user_id"],
            "feedback_id": "fb-1",
            "session_id": kwargs.get("session_id"),
            "message_id": kwargs.get("message_id"),
            "vote": kwargs["vote"],
            "reason_code": kwargs.get("reason_code"),
            "reason_text": kwargs.get("reason_text"),
            "scope": kwargs.get("scope"),
            "feedback_text": kwargs.get("feedback_text"),
            "query": kwargs["query"],
            "response": kwargs["response"],
            "category": "Uncategorized",
            "sub_category": "Pending analysis",
            "suggested_action": "",
            "analysis_summary": "",
            "classifier_model": "",
            "classification_status": "pending",
            "classification_error": None,
            "created_at": "2026-04-11T00:00:00Z",
            "updated_at": "2026-04-11T00:00:00Z",
            "version": 1,
        }
        self.items.append(item)
        return item

    def schedule_analysis(self, *, user_id, feedback_id):
        self.scheduled.append((user_id, feedback_id))


@pytest.mark.unit
def test_create_feedback_returns_item_and_schedules_analysis(client: TestClient):
    fake = _FakeFeedbackService()
    client.app.dependency_overrides[get_feedback_service] = lambda: fake
    try:
        r = client.post(
            "/api/feedback",
            json={
                "vote": "dislike",
                "query": "What is NLP?",
                "response": "NLP is ...",
                "reason_code": "insufficient_information",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_feedback_service, None)

    assert r.status_code == 200
    body = r.json()
    assert body["feedback_id"] == "fb-1"
    assert body["classification_status"] == "pending"
    assert fake.scheduled == [("default", "fb-1")]


@pytest.mark.unit
def test_list_feedback_returns_user_items(client: TestClient):
    fake = _FakeFeedbackService()
    fake.items = [
        {
            "user_id": "default",
            "feedback_id": "fb-a",
            "session_id": "s-1",
            "message_id": None,
            "vote": "like",
            "reason_code": None,
            "reason_text": None,
            "query": "Q1",
            "response": "A1",
            "is_active": True,
            "category": "Content Quality",
            "sub_category": "Good",
            "suggested_action": "",
            "analysis_summary": "",
            "classifier_model": "",
            "classification_status": "completed",
            "classification_error": None,
            "created_at": "2026-04-11T00:00:00Z",
            "updated_at": "2026-04-11T00:00:00Z",
            "version": 1,
        }
    ]

    client.app.dependency_overrides[get_feedback_service] = lambda: fake
    try:
        r = client.get("/api/feedback", params={"session_id": "s-1"})
    finally:
        client.app.dependency_overrides.pop(get_feedback_service, None)

    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["feedback_id"] == "fb-a"


@pytest.mark.unit
def test_create_general_feedback_from_feedbacks_tab(client: TestClient):
    fake = _FakeFeedbackService()
    client.app.dependency_overrides[get_feedback_service] = lambda: fake
    try:
        r = client.post(
            "/api/feedback",
            json={
                "vote": "general",
                "scope": "Knowledge Explorer",
                "feedback_text": "Please improve retrieval explanations in the explorer view.",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_feedback_service, None)

    assert r.status_code == 200
    body = r.json()
    assert body["vote"] == "general"
    assert body["scope"] == "Knowledge Explorer"
    assert "improve retrieval explanations" in (body.get("feedback_text") or "")
