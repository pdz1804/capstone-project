from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(v: Any, default: int = 0) -> int:
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(v)
    except Exception:
        return default


def _to_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _message_id_now() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid.uuid4().hex[:8]}"


def _clean_title(raw: str | None, fallback: str = "New chat") -> str:
    text = (raw or "").strip()
    if not text:
        return fallback
    text = " ".join(text.split())
    return text[:120]


def _preview_text(raw: str, max_len: int = 140) -> str:
    text = " ".join((raw or "").split())
    return text


def _encode_cursor(key: Dict[str, Any] | None) -> str | None:
    if not key:
        return None
    payload = json.dumps(key, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str | None) -> Dict[str, Any] | None:
    raw = (cursor or "").strip()
    if not raw:
        return None
    try:
        data = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8")
        parsed = json.loads(data)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


class DynamoChatHistoryRepository:
    """Persists chat sessions and messages in DynamoDB.

    Sessions table (default: chatbot-session):
      PK=user_id (S), SK=session_id (S)

    Messages table (default: chatbot-messages):
      PK=session_id (S), SK=message_id (S)
    """

    def __init__(self, sessions_table_name: str, messages_table_name: str, region: Optional[str] = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        dynamodb = boto3.resource("dynamodb", region_name=self._region)
        self._sessions_table = dynamodb.Table(sessions_table_name)
        self._messages_table = dynamodb.Table(messages_table_name)

    @classmethod
    def from_env(cls) -> DynamoChatHistoryRepository:
        sessions = (os.getenv("DYNAMODB_CHATBOT_SESSIONS_TABLE") or "chatbot-session").strip() or "chatbot-session"
        messages = (os.getenv("DYNAMODB_CHATBOT_MESSAGES_TABLE") or "chatbot-messages").strip() or "chatbot-messages"
        return cls(sessions, messages)

    def create_session(
        self,
        *,
        user_id: str,
        session_id: str,
        title: str | None = None,
        pinned: bool = False,
    ) -> Dict[str, Any]:
        now = _iso_now()
        item = {
            "user_id": user_id,
            "session_id": session_id,
            "title": _clean_title(title),
            "pinned": bool(pinned),
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
            "last_message_at": None,
            "last_message_preview": None,
            "last_message_role": None,
        }
        try:
            self._sessions_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(session_id)",
            )
        except ClientError as e:
            code = (e.response.get("Error") or {}).get("Code")
            if code != "ConditionalCheckFailedException":
                raise
        current = self.get_session(user_id=user_id, session_id=session_id)
        return current or item

    def get_session(self, *, user_id: str, session_id: str) -> Dict[str, Any] | None:
        r = self._sessions_table.get_item(Key={"user_id": user_id, "session_id": session_id})
        item = r.get("Item")
        if not item:
            return None
        return self._normalize_session(item)

    def list_sessions(
        self,
        *,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        # Query full user scope first so sorting can prioritize pinned + recent updates.
        collected: List[Dict[str, Any]] = []
        eks: Dict[str, Any] | None = None
        while True:
            query_args: Dict[str, Any] = {
                "KeyConditionExpression": Key("user_id").eq(user_id),
            }
            if eks:
                query_args["ExclusiveStartKey"] = eks
            r = self._sessions_table.query(**query_args)
            items = r.get("Items") or []
            collected.extend(self._normalize_session(x) for x in items)
            eks = r.get("LastEvaluatedKey")
            if not eks or len(collected) >= 2000:
                break

        collected.sort(
            key=lambda x: (
                0 if x.get("pinned") else 1,
                x.get("updated_at") or "",
            ),
            reverse=False,
        )
        # reverse by updated_at while keeping pinned first
        pinned_items = [x for x in collected if x.get("pinned")]
        unpinned_items = [x for x in collected if not x.get("pinned")]
        pinned_items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        unpinned_items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        ordered = pinned_items + unpinned_items

        start = 0
        if cursor:
            try:
                start = max(0, int(cursor))
            except Exception:
                start = 0
        page_limit = max(1, min(int(limit), 100))
        page = ordered[start : start + page_limit]
        next_cursor = str(start + page_limit) if start + page_limit < len(ordered) else None
        return page, next_cursor

    def update_session(
        self,
        *,
        user_id: str,
        session_id: str,
        title: str | None = None,
        pinned: bool | None = None,
    ) -> Dict[str, Any] | None:
        current = self.get_session(user_id=user_id, session_id=session_id)
        if not current:
            return None

        expr_names: Dict[str, str] = {"#updated": "updated_at"}
        expr_vals: Dict[str, Any] = {":updated": _iso_now()}
        sets = ["#updated = :updated"]

        if title is not None:
            expr_names["#title"] = "title"
            expr_vals[":title"] = _clean_title(title, fallback=current.get("title") or "New chat")
            sets.append("#title = :title")
        if pinned is not None:
            expr_names["#pinned"] = "pinned"
            expr_vals[":pinned"] = bool(pinned)
            sets.append("#pinned = :pinned")

        self._sessions_table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        return self.get_session(user_id=user_id, session_id=session_id)

    def put_message(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        traces: list[dict[str, Any]] | None = None,
        suggestions: list[str] | None = None,
    ) -> Dict[str, Any]:
        now = _iso_now()
        message_id = _message_id_now()
        item: Dict[str, Any] = {
            "session_id": session_id,
            "message_id": message_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": now,
        }
        if traces:
            item["traces"] = traces
        if suggestions:
            item["suggestions"] = suggestions

        self._messages_table.put_item(Item=item)

        self._sessions_table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression=(
                "SET #title = if_not_exists(#title, :default_title), "
                "#pinned = if_not_exists(#pinned, :false), "
                "#created = if_not_exists(#created, :now), "
                "#updated = :now, "
                "#last_at = :now, "
                "#preview = :preview, "
                "#last_role = :last_role "
                "ADD #count :inc"
            ),
            ExpressionAttributeNames={
                "#title": "title",
                "#pinned": "pinned",
                "#created": "created_at",
                "#updated": "updated_at",
                "#last_at": "last_message_at",
                "#preview": "last_message_preview",
                "#last_role": "last_message_role",
                "#count": "message_count",
            },
            ExpressionAttributeValues={
                ":default_title": _clean_title(content),
                ":false": False,
                ":now": now,
                ":preview": _preview_text(content),
                ":last_role": role,
                ":inc": 1,
            },
        )

        return self._normalize_message(item)

    def list_messages(
        self,
        *,
        session_id: str,
        limit: int = 50,
        cursor: str | None = None,
        newest_first: bool = True,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        query_args: Dict[str, Any] = {
            "KeyConditionExpression": Key("session_id").eq(session_id),
            "Limit": max(1, min(int(limit), 200)),
            "ScanIndexForward": not newest_first,
        }
        eks = _decode_cursor(cursor)
        if eks:
            query_args["ExclusiveStartKey"] = eks

        r = self._messages_table.query(**query_args)
        items = [self._normalize_message(x) for x in (r.get("Items") or [])]
        next_cursor = _encode_cursor(r.get("LastEvaluatedKey"))
        return items, next_cursor

    def delete_session(self, *, user_id: str, session_id: str) -> None:
        # Delete messages first.
        eks: Dict[str, Any] | None = None
        while True:
            qargs: Dict[str, Any] = {
                "KeyConditionExpression": Key("session_id").eq(session_id),
                "ProjectionExpression": "session_id, message_id",
            }
            if eks:
                qargs["ExclusiveStartKey"] = eks
            r = self._messages_table.query(**qargs)
            for item in r.get("Items") or []:
                self._messages_table.delete_item(
                    Key={"session_id": item["session_id"], "message_id": item["message_id"]}
                )
            eks = r.get("LastEvaluatedKey")
            if not eks:
                break

        self._sessions_table.delete_item(Key={"user_id": user_id, "session_id": session_id})

    def _normalize_session(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "session_id": str(item.get("session_id") or ""),
            "user_id": str(item.get("user_id") or ""),
            "title": _clean_title(str(item.get("title") or ""), fallback="New chat"),
            "pinned": _to_bool(item.get("pinned"), False),
            "message_count": _to_int(item.get("message_count"), 0),
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
            "last_message_at": str(item.get("last_message_at") or "") or None,
            "last_message_preview": str(item.get("last_message_preview") or "") or None,
            "last_message_role": str(item.get("last_message_role") or "") or None,
        }

    def _normalize_message(self, item: Dict[str, Any]) -> Dict[str, Any]:
        traces = item.get("traces") or []
        suggestions = item.get("suggestions") or []
        return {
            "session_id": str(item.get("session_id") or ""),
            "message_id": str(item.get("message_id") or ""),
            "user_id": str(item.get("user_id") or ""),
            "role": str(item.get("role") or "assistant"),
            "content": str(item.get("content") or ""),
            "created_at": str(item.get("created_at") or ""),
            "traces": traces if isinstance(traces, list) else [],
            "suggestions": [str(x) for x in suggestions] if isinstance(suggestions, list) else [],
        }
