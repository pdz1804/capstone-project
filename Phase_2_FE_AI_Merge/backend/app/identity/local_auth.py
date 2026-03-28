from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64u_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("utf-8"))


class LocalAuthService:
    """Simple local account auth (PBKDF2 + signed token)."""

    def __init__(self) -> None:
        self._secret = os.getenv("LOCAL_AUTH_SECRET", "dev-local-auth-secret-change-me")
        self._ttl_seconds = int(os.getenv("LOCAL_AUTH_TOKEN_TTL_SECONDS", "2592000"))  # 30 days
        self._pbkdf2_iterations = int(os.getenv("LOCAL_AUTH_PBKDF2_ITERATIONS", "100000"))

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self._pbkdf2_iterations)
        return f"pbkdf2_sha256${self._pbkdf2_iterations}${_b64u(salt)}${_b64u(dk)}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algo, rounds_raw, salt_b64, digest_b64 = password_hash.split("$", 3)
            if algo != "pbkdf2_sha256":
                return False
            rounds = int(rounds_raw)
            salt = _b64u_decode(salt_b64)
            expected = _b64u_decode(digest_b64)
            got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
            return hmac.compare_digest(got, expected)
        except Exception:
            return False

    def create_access_token(self, uid: str, email: str) -> str:
        now = int(time.time())
        payload = {"uid": uid, "email": email, "iat": now, "exp": now + self._ttl_seconds, "provider": "local"}
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(self._secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        return f"{_b64u(payload_bytes)}.{_b64u(sig)}"

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        left, right = token.split(".", 1)
        payload_bytes = _b64u_decode(left)
        given_sig = _b64u_decode(right)
        expected_sig = hmac.new(self._secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(given_sig, expected_sig):
            raise ValueError("Invalid token signature")
        payload = json.loads(payload_bytes.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expired")
        if payload.get("provider") != "local":
            raise ValueError("Invalid token provider")
        return payload
