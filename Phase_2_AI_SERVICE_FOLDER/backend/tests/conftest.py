"""Shared fixtures: FastAPI TestClient (runs lifespan), env isolation."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _tests_use_local_file_storage(monkeypatch: pytest.MonkeyPatch):
    """Keep pytest hermetic when .env sets FILE_STORAGE_BACKEND=s3 (dotenv does not override existing keys)."""
    from app.storage.service import reset_file_storage_singleton

    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    reset_file_storage_singleton()
    yield
    reset_file_storage_singleton()


@pytest.fixture
def client() -> TestClient:
    """HTTP client against the full app (OpenAPI stack)."""
    from app.main import app

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
