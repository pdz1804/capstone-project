from __future__ import annotations

from app.main import _resolve_usage_user_id


class _Req:
    def __init__(self, method: str, headers: dict[str, str] | None = None) -> None:
        self.method = method
        self.headers = headers or {}


def test_resolve_usage_user_id_prefers_header_uid():
    req = _Req("POST", {"X-User-Id": "abc_user_1"})
    assert _resolve_usage_user_id(req) == "abc_user_1"


def test_resolve_usage_user_id_returns_none_when_header_missing():
    req = _Req("OPTIONS", {})
    assert _resolve_usage_user_id(req) is None


def test_resolve_usage_user_id_returns_none_when_header_sanitizes_to_default():
    req = _Req("POST", {"X-User-Id": "!!!"})
    assert _resolve_usage_user_id(req) is None
