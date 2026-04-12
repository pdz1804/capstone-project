from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_generation_models_endpoint_returns_curated_bedrock_allowlist(client: TestClient):
    cfg = {
        "generation": {
            "provider": "bedrock",
            "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock_region": "us-west-2",
        }
    }

    with patch("app.api.routes.search_routes.merged_runtime_settings", return_value=cfg):
        r = client.get("/api/search/generation-models")

    assert r.status_code == 200
    body = r.json()
    models = body.get("models") or []
    assert body.get("provider") == "bedrock"
    assert body.get("region") == "us-west-2"
    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in models
    assert "google.gemma-3-27b-it" in models
    assert "us.anthropic.claude-sonnet-4-20250514-v1:0" in models
    assert "us.anthropic.claude-sonnet-4-6" in models
    assert "anthropic.claude-sonnet-4-20250514-v1:0" not in models
    assert "anthropic.claude-sonnet-4-6" not in models
    assert "anthropic.claude-3-5-haiku-20241022-v1:0" not in models
    assert "us.anthropic.claude-3-5-haiku-20241022-v1:0" not in models


@pytest.mark.unit
def test_search_rejects_non_allowlisted_bedrock_generation_model(client: TestClient):
    cfg = {
        "generation": {
            "provider": "bedrock",
            "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock_region": "us-west-2",
        }
    }

    with patch("app.api.routes.search_routes.merged_runtime_settings", return_value=cfg):
        r = client.post(
            "/api/search",
            json={
                "query": "hello",
                "mode": "retrieval_generation",
                "generation_model": "not.allowed.model",
            },
        )

    assert r.status_code == 400
    assert "Unsupported generation_model" in (r.json().get("detail") or "")
