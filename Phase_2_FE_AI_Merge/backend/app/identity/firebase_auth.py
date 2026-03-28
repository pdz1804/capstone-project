from __future__ import annotations

import logging
import os

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import auth, credentials
except Exception:  # pragma: no cover - runtime environment dependent
    firebase_admin = None
    auth = None
    credentials = None


class FirebaseAuthService:
    def __init__(self) -> None:
        if firebase_admin is None:
            logger.warning("firebase_admin is not installed; Google/Firebase auth endpoints are unavailable")
            return
        if not firebase_admin._apps:
            key_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
            resolved = os.path.abspath(key_path)
            if not os.path.exists(key_path):
                logger.error(
                    "Firebase Admin not configured: missing service account file at %s "
                    "(set FIREBASE_SERVICE_ACCOUNT_PATH in .env)",
                    resolved,
                )
                return
            try:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized (%s)", resolved)
            except Exception as e:
                logger.exception("Firebase Admin failed to initialize from %s: %s", resolved, e)

    def _ensure_app(self) -> None:
        if firebase_admin is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="firebase_admin is not installed. Install backend dependencies to enable Google login.",
            )
        if not firebase_admin._apps:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Firebase Admin is not configured. Add firebase-service-account.json under the "
                    "backend folder (same project as the web client) or set FIREBASE_SERVICE_ACCOUNT_PATH."
                ),
            )

    def verify_token(self, id_token: str) -> dict:
        self._ensure_app()
        try:
            return auth.verify_id_token(id_token, clock_skew_seconds=60)
        except Exception as e:
            if "unexpected keyword argument 'clock_skew_seconds'" in str(e):
                try:
                    return auth.verify_id_token(id_token)
                except Exception as inner_e:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid credentials: {inner_e!s}",
                        headers={"WWW-Authenticate": "Bearer"},
                    ) from inner_e
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication credentials: {e!s}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    def get_user_from_token(self, id_token: str) -> dict:
        decoded = self.verify_token(id_token)
        return {
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "picture": decoded.get("picture"),
        }
