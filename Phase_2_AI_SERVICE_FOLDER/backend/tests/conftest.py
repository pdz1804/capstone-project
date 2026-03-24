"""Shared fixtures: FastAPI TestClient (runs lifespan), env isolation."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """HTTP client against the full app (OpenAPI stack)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clear_sagemaker_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure SageMaker inference flags do not leak between tests."""
    for key in (
        "USE_AWS_SAGEMAKER_INFERENCE",
        "AWS_REGION",
        "SAGEMAKER_ENDPOINT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
