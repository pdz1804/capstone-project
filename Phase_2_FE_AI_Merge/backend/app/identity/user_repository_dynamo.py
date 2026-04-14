from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, List, Optional

from boto3.dynamodb.conditions import Attr

from .schemas import UserCreate, UserUpdate, UserResponse

logger = logging.getLogger(__name__)

# Pagination limits to prevent timeouts on large scans
MAX_SCAN_ITERATIONS = 50  # Stop after scanning 50 pages (~10k items at 200 per page)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
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


class DynamoUserRepository:
    """User profiles in a DynamoDB table (partition key: uid)."""

    def __init__(self, table_name: str, region: Optional[str] = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        self._table = boto3.resource("dynamodb", region_name=self._region).Table(table_name)

    @classmethod
    def from_env(cls) -> DynamoUserRepository:
        name = (os.getenv("DYNAMODB_USERS_TABLE") or "").strip()
        if not name:
            raise RuntimeError(
                "DYNAMODB_USERS_TABLE is not set. Create a DynamoDB table with partition key `uid` (String)."
            )
        return cls(name)

    def get_by_id(self, uid: str) -> Optional[UserResponse]:
        r = self._table.get_item(Key={"uid": uid})
        item = r.get("Item")
        if not item:
            return None
        return _item_to_response(item)

    def get_item_by_email(self, email: str) -> Optional[dict[str, Any]]:
        norm = (email or "").strip().lower()
        if not norm:
            return None
        last_key = None
        iterations = 0
        while iterations < MAX_SCAN_ITERATIONS:
            iterations += 1
            kwargs: dict[str, Any] = {
                "FilterExpression": Attr("email").eq(norm),
                "Limit": 200,
            }
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            r = self._table.scan(**kwargs)
            items = r.get("Items") or []
            if items:
                return items[0]
            last_key = r.get("LastEvaluatedKey")
            if not last_key:
                break
        if iterations >= MAX_SCAN_ITERATIONS:
            logger.warning(f"get_item_by_email scan hit max iterations ({MAX_SCAN_ITERATIONS}) for email pattern")
        return None

    def get_item_by_username(self, username: str) -> Optional[dict[str, Any]]:
        norm = (username or "").strip().lower()
        if not norm:
            return None
        last_key = None
        iterations = 0
        while iterations < MAX_SCAN_ITERATIONS:
            iterations += 1
            kwargs: dict[str, Any] = {
                "FilterExpression": Attr("username").eq(norm),
                "Limit": 200,
            }
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            r = self._table.scan(**kwargs)
            items = r.get("Items") or []
            if items:
                return items[0]
            last_key = r.get("LastEvaluatedKey")
            if not last_key:
                break
        if iterations >= MAX_SCAN_ITERATIONS:
            logger.warning(f"get_item_by_username scan hit max iterations ({MAX_SCAN_ITERATIONS}) for username pattern")
        return None

    def get_by_email(self, email: str) -> Optional[UserResponse]:
        item = self.get_item_by_email(email)
        return _item_to_response(item) if item else None

    def create(self, user_in: UserCreate) -> UserResponse:
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
        self._table.put_item(Item=clean, ConditionExpression="attribute_not_exists(uid)")
        return _item_to_response(clean)

    def update(self, uid: str, user_in: UserUpdate) -> Optional[UserResponse]:
        db_user = self.get_by_id(uid)
        if not db_user:
            return None
        data = user_in.model_dump(exclude_unset=True)
        if not data:
            return db_user
        expr_names: dict[str, str] = {}
        expr_vals: dict[str, Any] = {}
        parts: list[str] = []
        idx = 0
        for k, v in data.items():
            if v is None:
                continue
            nk = f"#f{idx}"
            vk = f":v{idx}"
            idx += 1
            expr_names[nk] = k
            if k == "lastLogin" and isinstance(v, datetime):
                expr_vals[vk] = v.isoformat()
            else:
                expr_vals[vk] = v
            parts.append(f"{nk} = {vk}")
        if not parts:
            return db_user
        self._table.update_item(
            Key={"uid": uid},
            UpdateExpression="SET " + ", ".join(parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        return self.get_by_id(uid)

    def set_local_auth_credentials(self, uid: str, password_hash: str) -> Optional[UserResponse]:
        existing = self.get_by_id(uid)
        if not existing:
            return None
        self._table.update_item(
            Key={"uid": uid},
            UpdateExpression="SET #provider = :provider, #pwd = :pwd",
            ExpressionAttributeNames={
                "#provider": "authProvider",
                "#pwd": "passwordHash",
            },
            ExpressionAttributeValues={
                ":provider": "local",
                ":pwd": password_hash,
            },
        )
        return self.get_by_id(uid)

    def delete(self, uid: str) -> bool:
        existing = self.get_by_id(uid)
        if not existing:
            return False
        self._table.delete_item(Key={"uid": uid})
        return True

    def list(self, skip: int = 0, limit: int | None = 100) -> List[UserResponse]:
        skip_n = max(0, int(skip))

        if limit is None:
            items: list[dict[str, Any]] = []
            last_key = None
            while True:
                kwargs: dict[str, Any] = {"Limit": 1000}
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                r = self._table.scan(**kwargs)
                items.extend(r.get("Items") or [])
                last_key = r.get("LastEvaluatedKey")
                if not last_key:
                    break
            return [_item_to_response(x) for x in items[skip_n:]]

        limit_n = max(1, int(limit))
        want = max(1, limit_n + skip_n)
        items: list[dict[str, Any]] = []
        last_key = None
        while len(items) < want:
            kwargs: dict[str, Any] = {"Limit": min(1000, max(1, want - len(items)))}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            r = self._table.scan(**kwargs)
            items.extend(r.get("Items") or [])
            last_key = r.get("LastEvaluatedKey")
            if not last_key:
                break

        out = [_item_to_response(x) for x in items[skip_n : skip_n + limit_n]]
        return out
