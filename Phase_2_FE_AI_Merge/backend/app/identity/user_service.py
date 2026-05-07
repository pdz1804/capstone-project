from __future__ import annotations

import os
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


class UserService:
    def __init__(self, user_repo):
        self.user_repo = user_repo
        self.local_auth = LocalAuthService()

    def get_user_profile(self, uid: str) -> UserResponse:
        user = self.user_repo.get_by_id(uid)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if not bool(user.isActive):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
        return user

    def update_user_profile(self, uid: str, payload: UserUpdate) -> UserResponse:
        existing = self.user_repo.get_by_id(uid)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        update_data = payload.model_dump(exclude_unset=True)

        if "role" in update_data and update_data.get("role") is not None:
            role_norm = str(update_data.get("role") or "").strip().lower()
            if role_norm not in {"student", "instructor", "admin"}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
            update_data["role"] = role_norm

        if "username" in update_data and update_data.get("username") is not None:
            username_norm = str(update_data.get("username") or "").strip().lower()
            if username_norm:
                owner = self.user_repo.get_item_by_username(username_norm)
                if owner and str(owner.get("uid") or "") != uid:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
                update_data["username"] = username_norm
            else:
                update_data["username"] = None

        updated = self.user_repo.update(uid, UserUpdate(**update_data))
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
                username=(str(user_data.get("email") or "").split("@")[0] or None),
                displayName=user_data.get("name"),
                photoURL=user_data.get("picture"),
                isActive=True,
            )
            return self.user_repo.create(user_in)
        if not bool(existing.isActive):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
        upd = UserUpdate(
            displayName=user_data.get("name"),
            photoURL=user_data.get("picture"),
            lastLogin=datetime.now(timezone.utc),
        )
        u = self.user_repo.update(uid, upd)
        return u or existing

    def list_users(
        self,
        skip: int = 0,
        limit: int | None = 100,
        query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> List[UserResponse]:
        skip_n = max(0, int(skip))
        limit_n = None if limit is None else max(1, int(limit))
        q = (query or "").strip().lower()
        role_q = (role or "").strip().lower()

        if not q and not role_q and is_active is None:
            return self.user_repo.list(skip=skip_n, limit=limit_n)

        rows = self.user_repo.list(skip=0, limit=None)

        if q:
            rows = [
                x
                for x in rows
                if q in x.uid.lower()
                or q in x.email.lower()
                or q in (x.username or "").lower()
                or q in (x.displayName or "").lower()
            ]
        if role_q:
            rows = [x for x in rows if (x.role or "").lower() == role_q]
        if is_active is not None:
            rows = [x for x in rows if bool(x.isActive) == bool(is_active)]

        rows.sort(key=lambda x: (x.createdAt.isoformat() if x.createdAt else ""), reverse=True)
        if limit_n is None:
            return rows[skip_n:]
        return rows[skip_n : skip_n + limit_n]

    def create_user_by_admin(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
        role: str = "student",
        username: str | None = None,
    ) -> UserResponse:
        if len(password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

        role_norm = (role or "student").strip().lower()
        if role_norm not in {"student", "instructor", "admin"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

        norm_email = str(email).strip().lower()
        if self.user_repo.get_item_by_email(norm_email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        uname = (username or norm_email.split("@")[0]).strip().lower()
        if uname and self.user_repo.get_item_by_username(uname):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

        uid = f"local_{uuid4().hex[:24]}"
        created = self.user_repo.create(
            UserCreate(
                uid=uid,
                email=norm_email,
                username=uname,
                displayName=display_name or norm_email.split("@")[0],
                role=role_norm,
                isActive=True,
                authProvider="local",
                passwordHash=self.local_auth.hash_password(password),
            )
        )
        return created

    def delete_user(self, uid: str) -> bool:
        return self.user_repo.delete(uid)

    def set_user_active(self, uid: str, is_active: bool) -> UserResponse:
        updated = self.user_repo.update(uid, UserUpdate(isActive=is_active))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return updated

    def ensure_default_admin_account(self) -> UserResponse | None:
        enabled = str(os.getenv("ENABLE_DEFAULT_ADMIN_BOOTSTRAP", "true")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            return None

        default_username = (os.getenv("DEFAULT_ADMIN_USERNAME") or "admin").strip().lower()
        default_email = (os.getenv("DEFAULT_ADMIN_EMAIL") or "admin@local.dev").strip().lower()
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD") or "quangphu1804"
        now = datetime.now(timezone.utc)
        password_hash = self.local_auth.hash_password(default_password)

        all_users = self.user_repo.list(skip=0, limit=None)
        exact_email_users = [u for u in all_users if str(u.email or "").strip().lower() == default_email]
        exact_email_users.sort(key=lambda u: (u.createdAt.isoformat() if u.createdAt else ""))

        keep_user: UserResponse | None = exact_email_users[0] if exact_email_users else None
        if keep_user is None:
            keep_user = self.user_repo.create(
                UserCreate(
                    uid=f"local_admin_{uuid4().hex[:16]}",
                    email=default_email,
                    username=default_username,
                    displayName="System Admin",
                    role="admin",
                    isActive=True,
                    authProvider="local",
                    passwordHash=password_hash,
                )
            )
        else:
            keep_user = self.user_repo.update(
                keep_user.uid,
                UserUpdate(
                    username=default_username,
                    displayName="System Admin",
                    role="admin",
                    isActive=True,
                    lastLogin=now,
                ),
            ) or keep_user
            keep_user = self.user_repo.set_local_auth_credentials(keep_user.uid, password_hash) or keep_user

        keep_uid = keep_user.uid

        all_users = self.user_repo.list(skip=0, limit=None)
        for user in all_users:
            if user.uid == keep_uid:
                continue
            same_email = str(user.email or "").strip().lower() == default_email
            same_username = str(user.username or "").strip().lower() == default_username
            # Only remove true duplicates of the default admin identity.
            #
            # Important: do NOT delete other admin users. Admins may be promoted via the UI,
            # and deleting them would cause their role to "revert" after a restart (record
            # gets recreated on next login with default role).
            if same_email or same_username:
                self.user_repo.delete(user.uid)

        final_user = self.user_repo.get_by_id(keep_uid)
        if final_user is None:
            return None

        final_user = self.user_repo.update(
            keep_uid,
            UserUpdate(
                username=default_username,
                displayName="System Admin",
                role="admin",
                isActive=True,
                lastLogin=now,
            ),
        ) or final_user
        final_user = self.user_repo.set_local_auth_credentials(keep_uid, password_hash) or final_user
        return final_user

    def register_local_account(self, payload: LocalRegisterRequest) -> AuthSessionResponse:
        if len(payload.password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
        existing = self.user_repo.get_item_by_email(str(payload.email))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        username = (payload.username or str(payload.email).split("@")[0]).strip().lower()
        if username and self.user_repo.get_item_by_username(username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

        uid = f"local_{uuid4().hex[:24]}"
        requested_role = (payload.role or "student").strip().lower()
        if requested_role not in {"student", "instructor"}:
            requested_role = "student"
        user_in = UserCreate(
            uid=uid,
            email=str(payload.email).lower(),
            username=username,
            displayName=payload.displayName or str(payload.email).split("@")[0],
            role=requested_role,
            isActive=True,
            photoURL=None,
            authProvider="local",
            passwordHash=self.local_auth.hash_password(payload.password),
        )
        user = self.user_repo.create(user_in)
        token = self.local_auth.create_access_token(user.uid, user.email)
        return AuthSessionResponse(user=user, access_token=token, auth_provider="local")

    def login_local_account(self, payload: LocalLoginRequest) -> AuthSessionResponse:
        identifier = str(payload.email or "").strip().lower()
        if not identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username is required")

        if "@" in identifier:
            item = self.user_repo.get_item_by_email(identifier)
        else:
            item = self.user_repo.get_item_by_username(identifier)

        if not item:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not bool(item.get("isActive", True)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
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
