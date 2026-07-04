from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_search_route_calls_orchestrator_and_returns_payload(client: TestClient):
    fresh = {
        "query": "what is nlp",
        "text_results": [],
        "image_results": [],
        "answer": "fresh answer",
        "telemetry": {
            "steps_ms": {"retrieval_total": 123, "generation": 456, "total": 600},
            "cache": {"retrieval": {"hit": False}},
        },
    }

    with patch("app.api.routes.search_routes.SearchOrchestrator") as MockOrch:
        MockOrch.return_value.run.return_value = fresh
        r = client.post(
            "/api/search",
            json={
                "query": "what is nlp",
                "top_k": 5,
                "retriever_type": "hybrid",
                "include_images": False,
                "images_for_generation": 0,
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "fresh answer"
    assert body["telemetry"]["steps_ms"]["retrieval_total"] == 123
    assert MockOrch.return_value.run.call_count == 1


@pytest.mark.unit
def test_search_route_does_not_add_top_level_route_cache_field(client: TestClient):
    fresh = {
        "query": "what is rag",
        "text_results": [{"id": "c1", "text": "x"}],
        "image_results": [],
        "answer": "fresh answer",
        "telemetry": {
            "steps_ms": {"retrieval_total": 20, "generation": 40, "total": 65},
            "cache": {"retrieval": {"hit": True}},
        },
    }

    with patch("app.api.routes.search_routes.SearchOrchestrator") as MockOrch:
        MockOrch.return_value.run.return_value = fresh
        r = client.post(
            "/api/search",
            json={
                "query": "what is rag",
                "top_k": 5,
                "retriever_type": "hybrid",
                "include_images": False,
                "images_for_generation": 0,
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "fresh answer"
    assert "cache" not in body
