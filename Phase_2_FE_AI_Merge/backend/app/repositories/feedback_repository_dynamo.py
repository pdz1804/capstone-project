from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from decimal import Decimal


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(v: Any, default: int = 0) -> int:
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(v)
    except Exception:
        return default


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


class DynamoFeedbackRepository:
    """
    Feedback records in DynamoDB.
    PK: user_id (String), SK: feedback_id (String)
    """

    def __init__(self, table_name: str, region: str | None = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        self._table = boto3.resource("dynamodb", region_name=self._region).Table(table_name)

    @classmethod
    def from_env(cls) -> "DynamoFeedbackRepository":
        table_name = (os.getenv("DYNAMODB_FEEDBACK_TABLE") or "").strip()
        if not table_name:
            raise RuntimeError(
                "DYNAMODB_FEEDBACK_TABLE is not set. Create table with PK=user_id (S), SK=feedback_id (S)."
            )
        return cls(table_name)

    def create_feedback(
        self,
        *,
        user_id: str,
        vote: str,
        query: str,
        response: str,
        session_id: str | None = None,
        message_id: str | None = None,
        reason_code: str | None = None,
        reason_text: str | None = None,
        scope: str | None = None,
        feedback_text: str | None = None,
    ) -> Dict[str, Any]:
        feedback_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid.uuid4().hex[:8]}"
        now = _iso_now()
        item: Dict[str, Any] = {
            "user_id": str(user_id),
            "feedback_id": feedback_id,
            "vote": str(vote),
            "query": str(query),
            "response": str(response),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "classification_status": "pending",
            "category": "Uncategorized",
            "sub_category": "Pending analysis",
            "suggested_action": "",
            "classifier_model": "",
            "analysis_summary": "",
        }
        if session_id:
            item["session_id"] = str(session_id)
        if message_id:
            item["message_id"] = str(message_id)
        if reason_code:
            item["reason_code"] = str(reason_code)
        if reason_text:
            item["reason_text"] = str(reason_text)
        if scope:
            item["scope"] = str(scope)
        if feedback_text:
            item["feedback_text"] = str(feedback_text)

        self._table.put_item(Item=item)
        return self._normalize_item(item)

    def get_feedback(self, *, user_id: str, feedback_id: str) -> Dict[str, Any] | None:
        r = self._table.get_item(Key={"user_id": user_id, "feedback_id": feedback_id})
        item = r.get("Item")
        if not item:
            return None
        return self._normalize_item(item)

    def list_feedback(
        self,
        *,
        user_id: str,
        limit: int = 30,
        cursor: str | None = None,
        category: str | None = None,
        session_id: str | None = None,
        is_active: bool | None = True,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        query_args: Dict[str, Any] = {
            "KeyConditionExpression": "user_id = :uid",
            "ExpressionAttributeValues": {":uid": user_id},
            "ScanIndexForward": False,
            "Limit": max(1, min(int(limit), 100)),
        }
        eks = _decode_cursor(cursor)
        if eks:
            query_args["ExclusiveStartKey"] = eks

        r = self._table.query(**query_args)
        items = [self._normalize_item(x) for x in (r.get("Items") or [])]

        wanted = str(category or "").strip().lower()
        if wanted:
            items = [x for x in items if str(x.get("category") or "").strip().lower() == wanted]

        wanted_session = str(session_id or "").strip()
        if wanted_session:
            items = [x for x in items if str(x.get("session_id") or "") == wanted_session]

        if is_active is not None:
            items = [x for x in items if bool(x.get("is_active", True)) == bool(is_active)]

        next_cursor = _encode_cursor(r.get("LastEvaluatedKey"))
        return items, next_cursor

    def list_feedback_all(
        self,
        *,
        limit: int = 500,
        user_id: str | None = None,
        category: str | None = None,
        vote: str | None = None,
        is_active: bool | None = None,
        query: str | None = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        last_key = None
        while True:
            kwargs: Dict[str, Any] = {"Limit": min(max(limit, 1), 1000)}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = self._table.scan(**kwargs)
            items.extend(self._normalize_item(x) for x in (resp.get("Items") or []))
            if len(items) >= limit:
                break
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        user_q = (user_id or "").strip().lower()
        category_q = (category or "").strip().lower()
        vote_q = (vote or "").strip().lower()
        text_q = (query or "").strip().lower()

        if user_q:
            items = [x for x in items if str(x.get("user_id") or "").lower() == user_q]
        if category_q:
            items = [x for x in items if str(x.get("category") or "").lower() == category_q]
        if vote_q:
            items = [x for x in items if str(x.get("vote") or "").lower() == vote_q]
        if is_active is not None:
            items = [x for x in items if bool(x.get("is_active", True)) == bool(is_active)]
        if text_q:
            items = [
                x
                for x in items
                if text_q in str(x.get("query") or "").lower()
                or text_q in str(x.get("response") or "").lower()
                or text_q in str(x.get("feedback_text") or "").lower()
                or text_q in str(x.get("reason_text") or "").lower()
                or text_q in str(x.get("feedback_id") or "").lower()
                or text_q in str(x.get("user_id") or "").lower()
            ]

        items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        return items[:limit]

    def update_analysis(
        self,
        *,
        user_id: str,
        feedback_id: str,
        category: str,
        sub_category: str,
        suggested_action: str,
        analysis_summary: str,
        classifier_model: str,
        classification_status: str,
        classification_error: str | None = None,
    ) -> Dict[str, Any] | None:
        expr_names = {
            "#updated": "updated_at",
            "#category": "category",
            "#sub": "sub_category",
            "#action": "suggested_action",
            "#summary": "analysis_summary",
            "#model": "classifier_model",
            "#status": "classification_status",
        }
        expr_vals: Dict[str, Any] = {
            ":updated": _iso_now(),
            ":category": category,
            ":sub": sub_category,
            ":action": suggested_action,
            ":summary": analysis_summary,
            ":model": classifier_model,
            ":status": classification_status,
        }
        sets = [
            "#updated = :updated",
            "#category = :category",
            "#sub = :sub",
            "#action = :action",
            "#summary = :summary",
            "#model = :model",
            "#status = :status",
        ]
        if classification_error is not None:
            expr_names["#err"] = "classification_error"
            expr_vals[":err"] = classification_error
            sets.append("#err = :err")

        self._table.update_item(
            Key={"user_id": user_id, "feedback_id": feedback_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        return self.get_feedback(user_id=user_id, feedback_id=feedback_id)

    def update_feedback_admin(self, *, user_id: str, feedback_id: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
        current = self.get_feedback(user_id=user_id, feedback_id=feedback_id)
        if not current:
            return None

        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            return current

        expr_names: Dict[str, str] = {"#updated": "updated_at"}
        expr_vals: Dict[str, Any] = {":updated": _iso_now()}
        sets = ["#updated = :updated"]

        idx = 0
        for k, v in clean.items():
            nk = f"#f{idx}"
            vk = f":v{idx}"
            idx += 1
            expr_names[nk] = k
            expr_vals[vk] = v
            sets.append(f"{nk} = {vk}")

        self._table.update_item(
            Key={"user_id": user_id, "feedback_id": feedback_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        return self.get_feedback(user_id=user_id, feedback_id=feedback_id)

    def delete_feedback(self, *, user_id: str, feedback_id: str) -> bool:
        current = self.get_feedback(user_id=user_id, feedback_id=feedback_id)
        if not current:
            return False
        self._table.delete_item(Key={"user_id": user_id, "feedback_id": feedback_id})
        return True

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": str(item.get("user_id") or ""),
            "feedback_id": str(item.get("feedback_id") or ""),
            "session_id": str(item.get("session_id") or "") or None,
            "message_id": str(item.get("message_id") or "") or None,
            "vote": str(item.get("vote") or ""),
            "reason_code": str(item.get("reason_code") or "") or None,
            "reason_text": str(item.get("reason_text") or "") or None,
            "scope": str(item.get("scope") or "") or None,
            "feedback_text": str(item.get("feedback_text") or "") or None,
            "query": str(item.get("query") or ""),
            "response": str(item.get("response") or ""),
            "is_active": bool(item.get("is_active", True)),
            "category": str(item.get("category") or "Uncategorized"),
            "sub_category": str(item.get("sub_category") or ""),
            "suggested_action": str(item.get("suggested_action") or ""),
            "analysis_summary": str(item.get("analysis_summary") or ""),
            "classifier_model": str(item.get("classifier_model") or ""),
            "classification_status": str(item.get("classification_status") or "pending"),
            "classification_error": str(item.get("classification_error") or "") or None,
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
            "version": _to_int(item.get("version"), 1),
        }
