from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from .schemas import UserCreate, UserResponse, UserUpdate


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _item_to_response(item: dict[str, Any]) -> UserResponse:
    return UserResponse(
        uid=item["uid"],
        email=item["email"],
        username=item.get("username"),
        displayName=item.get("displayName"),
        role=item.get("role") or "student",
        isActive=bool(item.get("isActive", True)),
        photoURL=item.get("photoURL"),
        persona=item.get("persona"),
        educationDescription=item.get("educationDescription"),
        authProvider=item.get("authProvider"),
        createdAt=_parse_dt(item.get("createdAt")) or datetime.now(timezone.utc),
        lastLogin=_parse_dt(item.get("lastLogin")),
    )


class LocalFileUserRepository:
    """Small JSON-backed user repository for local development."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._lock = threading.Lock()
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._file_path.write_text("[]\n", encoding="utf-8")

    @classmethod
    def default_path(cls) -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "users.local.json"

    @classmethod
    def from_env(cls) -> "LocalFileUserRepository":
        return cls(cls.default_path())

    def _read_items_unlocked(self) -> list[dict[str, Any]]:
        try:
            raw = self._file_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return []
        if not raw:
            return []
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"Invalid user store format in {self._file_path}")
        return [item for item in data if isinstance(item, dict)]

    def _write_items_unlocked(self, items: list[dict[str, Any]]) -> None:
        self._file_path.write_text(
            json.dumps(items, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _with_items(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_items_unlocked()

    def get_by_id(self, uid: str) -> Optional[UserResponse]:
        for item in self._with_items():
            if str(item.get("uid") or "") == uid:
                return _item_to_response(item)
        return None

    def get_item_by_email(self, email: str) -> Optional[dict[str, Any]]:
        norm = (email or "").strip().lower()
        if not norm:
            return None
        for item in self._with_items():
            if str(item.get("email") or "").strip().lower() == norm:
                return item
        return None

    def get_item_by_username(self, username: str) -> Optional[dict[str, Any]]:
        norm = (username or "").strip().lower()
        if not norm:
            return None
        for item in self._with_items():
            if str(item.get("username") or "").strip().lower() == norm:
                return item
        return None

    def get_by_email(self, email: str) -> Optional[UserResponse]:
        item = self.get_item_by_email(email)
        return _item_to_response(item) if item else None

    def create(self, user_in: UserCreate) -> UserResponse:
        with self._lock:
            items = self._read_items_unlocked()
            if any(str(item.get("uid") or "") == user_in.uid for item in items):
                raise ValueError(f"User {user_in.uid} already exists")

            now = _iso_now()
            item = {
                "uid": user_in.uid,
                "email": str(user_in.email).lower(),
                "username": (str(user_in.username).strip().lower() if user_in.username else None),
                "displayName": user_in.displayName,
                "role": user_in.role or "student",
                "isActive": bool(user_in.isActive),
                "photoURL": user_in.photoURL,
                "persona": user_in.persona,
                "educationDescription": user_in.educationDescription,
                "authProvider": user_in.authProvider,
                "passwordHash": user_in.passwordHash,
                "createdAt": now,
                "lastLogin": now,
            }
            clean = {k: v for k, v in item.items() if v is not None}
            items.append(clean)
            self._write_items_unlocked(items)
        return _item_to_response(clean)

    def update(self, uid: str, user_in: UserUpdate) -> Optional[UserResponse]:
        with self._lock:
            items = self._read_items_unlocked()
            for item in items:
                if str(item.get("uid") or "") != uid:
                    continue
                data = user_in.model_dump(exclude_unset=True)
                for key, value in data.items():
                    if value is None:
                        continue
                    item[key] = value.isoformat() if isinstance(value, datetime) else value
                self._write_items_unlocked(items)
                return _item_to_response(item)
        return None

    def set_local_auth_credentials(self, uid: str, password_hash: str) -> Optional[UserResponse]:
        with self._lock:
            items = self._read_items_unlocked()
            for item in items:
                if str(item.get("uid") or "") != uid:
                    continue
                item["authProvider"] = "local"
                item["passwordHash"] = password_hash
                self._write_items_unlocked(items)
                return _item_to_response(item)
        return None

    def delete(self, uid: str) -> bool:
        with self._lock:
            items = self._read_items_unlocked()
            filtered = [item for item in items if str(item.get("uid") or "") != uid]
            if len(filtered) == len(items):
                return False
            self._write_items_unlocked(filtered)
        return True

    def list(self, skip: int = 0, limit: int | None = 100) -> List[UserResponse]:
        items = self._with_items()
        items.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
        rows = [_item_to_response(item) for item in items]
        skip_n = max(0, int(skip))
        if limit is None:
            return rows[skip_n:]
        limit_n = max(0, int(limit))
        return rows[skip_n : skip_n + limit_n]
