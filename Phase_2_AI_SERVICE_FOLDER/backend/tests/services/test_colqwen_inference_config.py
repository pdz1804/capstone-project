"""ColQwenInferenceService flags (no model load)."""

from __future__ import annotations

import pytest

from app.services.colqwen_inference import ColQwenInferenceService, _bool_from_cfg


@pytest.mark.unit
def test_bool_from_cfg():
    assert _bool_from_cfg({"use_aws_sagemaker": True}) is True
    assert _bool_from_cfg({"use_aws_sagemaker": "true"}) is True
    assert _bool_from_cfg({"use_aws_sagemaker": False}) is False


@pytest.mark.unit
def test_use_sagemaker_env_over_yaml(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_AWS_SAGEMAKER_INFERENCE", "1")
    svc = ColQwenInferenceService(
        {"inference": {"use_aws_sagemaker": False}, "image_retrieval": {"colqwen": {}}}
    )
    assert svc.use_sagemaker is True


@pytest.mark.unit
def test_use_sagemaker_from_yaml(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("USE_AWS_SAGEMAKER_INFERENCE", raising=False)
    svc = ColQwenInferenceService(
        {"inference": {"use_aws_sagemaker": True}, "image_retrieval": {"colqwen": {}}}
    )
    assert svc.use_sagemaker is True
