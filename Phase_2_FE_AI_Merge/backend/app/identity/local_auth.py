from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64u_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("utf-8"))


class LocalAuthService:
    """Simple local account auth (PBKDF2 + signed token)."""

    def __init__(self) -> None:
        secret_env = os.getenv("LOCAL_AUTH_SECRET", "").strip()
        is_production = os.getenv("ENV", "development").lower() in ("production", "prod")

        # Validate or generate the secret
        if not secret_env:
            if is_production:
                raise RuntimeError(
                    "LOCAL_AUTH_SECRET is required in production mode. "
                    "Generate a strong 32-byte random secret and set it in your .env file.\n"
                    "Example: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            # Development: generate a temporary secret (log it for reference)
            self._secret = secrets.token_urlsafe(32)
            logger.warning(
                f"LOCAL_AUTH_SECRET not set; generated temporary dev secret. "
                f"DO NOT USE IN PRODUCTION: {self._secret}"
            )
        elif secret_env == "dev-local-auth-secret-change-me":
            raise RuntimeError(
                "LOCAL_AUTH_SECRET still contains the default insecure value. "
                "Please generate a strong secret and update your .env file.\n"
                "Example: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        else:
            self._secret = secret_env
            if len(secret_env) < 16:
                logger.warning(
                    f"LOCAL_AUTH_SECRET is only {len(secret_env)} bytes. "
                    "Consider using a longer secret (32+ bytes recommended)."
                )

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
        except (ValueError, KeyError, IndexError) as e:
            logger.debug(f"Password verification failed: {type(e).__name__}")
            return False

    def create_access_token(self, uid: str, email: str) -> str:
        """Create a signed access token with validation of required fields."""
        # Validate that both uid and email are non-empty
        if not uid or not str(uid).strip():
            raise ValueError("uid must be a non-empty string")
        if not email or not str(email).strip():
            raise ValueError("email must be a non-empty string")

        now = int(time.time())
        payload = {"uid": uid, "email": email, "iat": now, "exp": now + self._ttl_seconds, "provider": "local"}
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(self._secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        return f"{_b64u(payload_bytes)}.{_b64u(sig)}"

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        try:
            left, right = token.split(".", 1)
            if not left or not right:
                raise ValueError("Token format invalid: empty payload or signature")
        except (ValueError, AttributeError) as e:
            logger.debug(f"Token split failed: {e}")
            raise ValueError("Invalid token format") from e

        try:
            payload_bytes = _b64u_decode(left)
            given_sig = _b64u_decode(right)
        except (ValueError, IndexError) as e:
            logger.debug(f"Token decoding failed: {e}")
            raise ValueError("Invalid token encoding") from e

        expected_sig = hmac.new(self._secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(given_sig, expected_sig):
            raise ValueError("Invalid token signature")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            logger.debug(f"Token payload JSON parsing failed: {e}")
            raise ValueError("Invalid token payload") from e

        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expired")
        if payload.get("provider") != "local":
            raise ValueError("Invalid token provider")
        return payload
