"""qdrant_errors helper classification."""

from __future__ import annotations

import pytest

from app.core.qdrant_errors import is_qdrant_unreachable, qdrant_setup_hint


@pytest.mark.unit
def test_is_qdrant_unreachable_winerror():
    assert is_qdrant_unreachable(RuntimeError("[WinError 10061] No connection")) is True


@pytest.mark.unit
def test_is_qdrant_unreachable_refused():
    assert is_qdrant_unreachable(ConnectionError("Connection refused")) is True


@pytest.mark.unit
def test_is_qdrant_unreachable_errno_99():
    assert is_qdrant_unreachable(RuntimeError("[Errno 99] Cannot assign requested address")) is True


@pytest.mark.unit
def test_qdrant_setup_hint_docker():
    s = qdrant_setup_hint({"qdrant": {"mode": "docker", "host": "127.0.0.1", "port": 6333}})
    assert "6333" in s and "docker" in s.lower()
    assert "host.docker.internal" in s
