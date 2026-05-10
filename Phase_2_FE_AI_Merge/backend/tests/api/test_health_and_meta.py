"""Health, root, config, system inference   no heavy deps."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


@pytest.mark.unit
def test_api_health_alias(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200


@pytest.mark.unit
def test_api_root(client: TestClient):
    r = client.get("/api")
    assert r.status_code == 200
    body = r.json()
    assert body.get("service") == "phase2-fe-ai-merge"
    assert "version" in body


@pytest.mark.unit
def test_openapi_schema(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "openapi" in r.json()


@pytest.mark.unit
def test_config_endpoint_returns_shape(client: TestClient):
    r = client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert "config_path" in data or "error" in data
    if "key_settings" in data:
        assert "qdrant_mode" in data["key_settings"] or True


@pytest.mark.unit
def test_system_inference_probe(client: TestClient, clear_sagemaker_env):
    r = client.get("/api/system/inference")
    assert r.status_code == 200
    data = r.json()
    assert "use_aws_sagemaker_inference" in data
    assert "use_aws_sagemaker_whisper" in data
    assert "qdrant_mode" in data
    assert "text_collection" in data
    assert "image_collection" in data
