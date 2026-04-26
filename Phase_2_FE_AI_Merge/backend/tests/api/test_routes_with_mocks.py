"""POST routes: mock services so CI does not need GPU, Qdrant, or real files."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_search_mocked(client: TestClient):
    fake = {
        "query": "test",
        "text_results": [{"id": "c1", "text": "hello", "source": "s.md", "score": 0.9, "rank": 1}],
        "image_results": [],
        "answer": "mocked",
    }
    with patch("app.api.routes.search_routes.SearchOrchestrator") as MockOrch:
        MockOrch.return_value.run.return_value = fake
        r = client.post(
            "/api/search",
            json={
                "query": "test query",
                "top_k": 5,
                "retriever_type": "hybrid",
                "include_images": False,
                "images_for_generation": 0,
            },
        )
    assert r.status_code == 200
    assert r.json()["answer"] == "mocked"


@pytest.mark.unit
def test_search_qdrant_unreachable_returns_503(client: TestClient):
    with patch("app.api.routes.search_routes.SearchOrchestrator") as MockOrch:
        MockOrch.return_value.run.side_effect = RuntimeError("[Errno 99] Cannot assign requested address")
        r = client.post(
            "/api/search",
            json={
                "query": "test query",
                "top_k": 5,
                "retriever_type": "dense",
                "include_images": False,
                "images_for_generation": 0,
            },
        )
    assert r.status_code == 503
    assert "Cannot connect to Qdrant" in r.json()["detail"]


@pytest.mark.unit
def test_process_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.run_processing") as mock_run:
        mock_run.return_value = {"status": "ok", "stages": []}
        r = client.post("/api/process", params={"force": False})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


@pytest.mark.unit
def test_index_all_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.IndexingService") as MockSvc:
        inst = MockSvc.return_value
        inst.index_all.return_value = {
            "text": {"status": "ok", "chunks": 0},
            "image": {"status": "ok", "pages": 0},
        }
        r = client.post("/api/index", params={"force": False})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


@pytest.mark.unit
def test_index_text_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.IndexingService") as MockSvc:
        MockSvc.return_value.index_text.return_value = {"status": "ok", "chunks": 1}
        r = client.post("/api/index/text", params={"force": False})
    assert r.status_code == 200


@pytest.mark.unit
def test_index_image_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.IndexingService") as MockSvc:
        MockSvc.return_value.index_images.return_value = {"status": "ok", "pages": 0}
        r = client.post("/api/index/image", params={"force": False})
    assert r.status_code == 200


@pytest.mark.unit
def test_index_remove_text_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.IndexingService") as MockSvc:
        MockSvc.return_value.remove_from_index.return_value = {
            "status": "ok",
            "text": {"removed_qdrant_points": 2, "removed_documents_json_chunks": 2},
            "image": None,
        }
        r = client.post(
            "/api/index/remove",
            json={"text_source": "D:/proj/stage4_rag_ready/foo/foo.md"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    MockSvc.return_value.remove_from_index.assert_called_once()


@pytest.mark.unit
def test_index_remove_clear_image_mocked(client: TestClient):
    with patch("app.api.routes.pipeline_routes.IndexingService") as MockSvc:
        MockSvc.return_value.remove_from_index.return_value = {
            "status": "ok",
            "text": None,
            "image": {"cleared_collection": True, "previous_point_count": 5},
        }
        r = client.post("/api/index/remove", json={"clear_image_index": True})
    assert r.status_code == 200


@pytest.mark.unit
def test_index_remove_requires_action(client: TestClient):
    r = client.post("/api/index/remove", json={})
    assert r.status_code == 422


@pytest.mark.unit
def test_insights_summary_mocked(client: TestClient):
    with patch("app.api.routes.insights_routes.InsightsService") as MockSvc:
        MockSvc.return_value.lecture_summary.return_value = {"summary": "# OK", "depth": "brief"}
        r = client.post(
            "/api/insights/summary",
            json={"focus_query": "x", "depth": "brief", "top_k": 5},
        )
    assert r.status_code == 200
    assert "summary" in r.json()


@pytest.mark.unit
def test_insights_visualization_mocked(client: TestClient):
    with patch("app.api.routes.insights_routes.InsightsService") as MockSvc:
        MockSvc.return_value.lecture_visualization.return_value = {
            "image_base64": "YQo=",
            "mime_type": "image/png",
            "model_text": "Here is a summary caption.",
            "error": None,
        }
        r = client.post(
            "/api/insights/visualization",
            json={"topic": "chapter 1", "document_id": None},
        )
    assert r.status_code == 200
    body = r.json()
    assert body.get("image_base64")
    assert body.get("mime_type") == "image/png"
    assert body.get("model_text")


@pytest.mark.unit
def test_insights_mcq_mocked(client: TestClient):
    with patch("app.api.routes.insights_routes.InsightsService") as MockSvc:
        MockSvc.return_value.mcq_quiz.return_value = {"questions": [], "topic": "t"}
        r = client.post(
            "/api/insights/mcq",
            json={"topic": "algebra", "num_questions": 3, "difficulty": "basic"},
        )
    assert r.status_code == 200


@pytest.mark.unit
def test_insights_roadmap_mocked(client: TestClient):
    with patch("app.api.routes.insights_routes.InsightsService") as MockSvc:
        MockSvc.return_value.learning_roadmap.return_value = {"roadmap": "## Plan"}
        r = client.post(
            "/api/insights/learning-roadmap",
            json={"student_profile": "u", "goals": "pass exam"},
        )
    assert r.status_code == 200


@pytest.mark.unit
def test_insights_analytics(client: TestClient):
    r = client.get("/api/insights/analytics")
    assert r.status_code == 200
    assert "message" in r.json() or "metrics" in r.json()
