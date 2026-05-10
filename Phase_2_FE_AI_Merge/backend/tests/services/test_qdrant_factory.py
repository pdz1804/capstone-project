"""Qdrant client factory   mock gRPC/HTTP client."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_build_qdrant_client_docker_calls_constructor():
    with patch("qdrant_client.QdrantClient", autospec=True) as QC:
        from app.repositories.qdrant_factory import build_qdrant_client

        build_qdrant_client({"qdrant": {"mode": "docker", "host": "localhost", "port": 6333}})
        QC.assert_called_once()
        call_kw = QC.call_args[1]
        assert call_kw.get("host") == "localhost"
        assert call_kw.get("port") == 6333


@pytest.mark.unit
def test_build_qdrant_client_cloud_requires_url():
    from app.repositories.qdrant_factory import build_qdrant_client

    with pytest.raises(ValueError, match="qdrant.url"):
        build_qdrant_client({"qdrant": {"mode": "cloud", "url": "", "api_key": "x"}})
