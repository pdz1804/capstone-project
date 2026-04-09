from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from fastapi import HTTPException, status

from .local_auth import LocalAuthService
from .schemas import (
    AuthSessionResponse,
    LocalLoginRequest,
    LocalRegisterRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from .user_repository_dynamo import DynamoUserRepository


class UserService:
    def __init__(self, user_repo: DynamoUserRepository):
        self.user_repo = user_repo
        self.local_auth = LocalAuthService()

    def get_user_profile(self, uid: str) -> UserResponse:
        user = self.user_repo.get_by_id(uid)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def update_user_profile(self, uid: str, payload: UserUpdate) -> UserResponse:
        updated = self.user_repo.update(uid, payload)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return updated

    def sync_user(self, user_data: dict) -> UserResponse:
        uid = user_data.get("uid")
        existing = self.user_repo.get_by_id(uid)
        if not existing:
            user_in = UserCreate(
                uid=uid,
                email=user_data.get("email"),
                displayName=user_data.get("name"),
                photoURL=user_data.get("picture"),
            )
            return self.user_repo.create(user_in)
        upd = UserUpdate(
            displayName=user_data.get("name"),
            photoURL=user_data.get("picture"),
            lastLogin=datetime.now(timezone.utc),
        )
        u = self.user_repo.update(uid, upd)
        return u or existing

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        return self.user_repo.list(skip=skip, limit=limit)

    def register_local_account(self, payload: LocalRegisterRequest) -> AuthSessionResponse:
        if len(payload.password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
        existing = self.user_repo.get_item_by_email(str(payload.email))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        uid = f"local_{uuid4().hex[:24]}"
        user_in = UserCreate(
            uid=uid,
            email=str(payload.email).lower(),
            displayName=payload.displayName or str(payload.email).split("@")[0],
            photoURL=None,
            authProvider="local",
            passwordHash=self.local_auth.hash_password(payload.password),
        )
        user = self.user_repo.create(user_in)
        token = self.local_auth.create_access_token(user.uid, user.email)
        return AuthSessionResponse(user=user, access_token=token, auth_provider="local")

    def login_local_account(self, payload: LocalLoginRequest) -> AuthSessionResponse:
        item = self.user_repo.get_item_by_email(str(payload.email).lower())
        if not item:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if (item.get("authProvider") or "google") != "local":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is linked to Google login. Please sign in with Google.",
            )
        password_hash = item.get("passwordHash") or ""
        if not self.local_auth.verify_password(payload.password, password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        user = self.user_repo.update(
            item["uid"],
            UserUpdate(lastLogin=datetime.now(timezone.utc)),
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        token = self.local_auth.create_access_token(user.uid, user.email)
        return AuthSessionResponse(user=user, access_token=token, auth_provider="local")

    def get_user_from_local_token(self, token: str) -> UserResponse:
        try:
            payload = self.local_auth.verify_access_token(token)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local auth token")
        uid = str(payload.get("uid") or "")
        if not uid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local auth token")
        return self.get_user_profile(uid)
