from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(v: Any, default: int = 0) -> int:
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(v)
    except Exception:
        return default


class DynamoQuizResultsRepository:
    """
    Quiz attempt results in DynamoDB.
    PK: user_id (String), SK: attempt_id (String, uuid or time-ordered id)
    """

    def __init__(self, table_name: str, region: Optional[str] = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        self._table = boto3.resource("dynamodb", region_name=self._region).Table(table_name)

    @classmethod
    def from_env(cls) -> DynamoQuizResultsRepository:
        name = (os.getenv("DYNAMODB_QUIZ_RESULTS_TABLE") or "").strip()
        if not name:
            raise RuntimeError(
                "DYNAMODB_QUIZ_RESULTS_TABLE is not set. Create DynamoDB table with PK=user_id (S), SK=attempt_id (S)."
            )
        return cls(name)

    def create_attempt(
        self,
        *,
        user_id: str,
        score: int,
        total: int,
        file_id: int | None = None,
        document_id: str | None = None,
        quiz_topic: str | None = None,
    ) -> Dict[str, Any]:
        attempt_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid.uuid4().hex[:8]}"
        now = _iso_now()
        item: Dict[str, Any] = {
            "user_id": user_id,
            "attempt_id": attempt_id,
            "score": int(score),
            "total": int(total),
            "created_at": now,
        }
        if file_id is not None:
            item["file_id"] = int(file_id)
        if document_id:
            item["document_id"] = document_id
        if quiz_topic:
            item["quiz_topic"] = quiz_topic
        self._table.put_item(Item=item)
        return item

    def list_attempts(self, user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        r = self._table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
            Limit=max(1, min(int(limit), 1000)),
        )
        items = r.get("Items") or []
        out: List[Dict[str, Any]] = []
        for it in items:
            out.append(
                {
                    "attempt_id": str(it.get("attempt_id") or ""),
                    "user_id": str(it.get("user_id") or ""),
                    "score": _to_int(it.get("score"), 0),
                    "total": _to_int(it.get("total"), 0),
                    "file_id": _to_int(it.get("file_id"), 0) if it.get("file_id") is not None else None,
                    "document_id": str(it.get("document_id") or "") or None,
                    "quiz_topic": str(it.get("quiz_topic") or "") or None,
                    "created_at": str(it.get("created_at") or ""),
                }
            )
        return out
