from __future__ import annotations

import json
import logging
import os
import tempfile

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
            cred = self._load_firebase_credentials()
            if cred is None:
                return
            try:
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized")
            except Exception as e:
                logger.exception("Firebase Admin failed to initialize: %s", e)

    @staticmethod
    def _load_firebase_credentials():
        """Load Firebase credentials from environment variable or file.

        Priority:
        1. FIREBASE_SERVICE_ACCOUNT (JSON string in env var) - recommended for public code
        2. FIREBASE_SERVICE_ACCOUNT_PATH (file path) - legacy support
        """
        if firebase_admin is None or credentials is None:
            return None

        # Try environment variable first (recommended for cloud deployment)
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
        if service_account_json:
            try:
                cred_dict = json.loads(service_account_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("Firebase credentials loaded from FIREBASE_SERVICE_ACCOUNT env var")
                return cred
            except json.JSONDecodeError as e:
                logger.error("FIREBASE_SERVICE_ACCOUNT is not valid JSON: %s", e)
                return None
            except Exception as e:
                logger.error("Failed to load Firebase credentials from FIREBASE_SERVICE_ACCOUNT: %s", e)
                return None

        # Fallback to file path (legacy support)
        key_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
        if os.path.exists(key_path):
            try:
                cred = credentials.Certificate(key_path)
                logger.info("Firebase credentials loaded from file: %s", key_path)
                return cred
            except Exception as e:
                logger.error("Failed to load Firebase credentials from file %s: %s", key_path, e)
                return None

        # No credentials found
        logger.error(
            "Firebase Admin not configured. Set FIREBASE_SERVICE_ACCOUNT env var with JSON credentials "
            "(recommended) or FIREBASE_SERVICE_ACCOUNT_PATH with file path (legacy). "
            "Get credentials from Firebase Console > Project Settings > Service Accounts > Generate New Private Key"
        )
        return None

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
        email = decoded.get("email")
        uid = decoded.get("uid")

        if not email:
            logger.warning(f"Firebase token for UID {uid} missing email claim. Token claims: {list(decoded.keys())}")

        return {
            "uid": uid,
            "email": email,
            "name": decoded.get("name"),
            "picture": decoded.get("picture"),
        }
