"""app.core.paths merged_runtime_settings behaviour."""

from __future__ import annotations

import pytest

from app.core.paths import merged_runtime_settings, load_yaml_config


@pytest.mark.unit
def test_merged_runtime_applies_qdrant_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QDRANT_MODE", "cloud")
    monkeypatch.setenv("QDRANT_URL", "https://example.cloud.qdrant.io:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "k")
    cfg = merged_runtime_settings({"qdrant": {"mode": "docker", "host": "localhost", "port": 6333}})
    assert cfg["qdrant"]["mode"] == "cloud"
    assert cfg["qdrant"]["url"] == "https://example.cloud.qdrant.io:6333"


@pytest.mark.unit
def test_merged_runtime_sagemaker_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_AWS_SAGEMAKER_INFERENCE", "true")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    cfg = merged_runtime_settings({"inference": {"use_aws_sagemaker": False}})
    assert cfg["inference"]["use_aws_sagemaker"] is True
    assert cfg["inference"]["aws_region"] == "ap-southeast-1"


@pytest.mark.unit
def test_load_yaml_config_not_empty():
    cfg = load_yaml_config()
    assert isinstance(cfg, dict)
    assert "pipeline" in cfg
