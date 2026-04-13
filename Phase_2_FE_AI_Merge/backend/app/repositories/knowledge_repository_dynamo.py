from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Attr


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value


class DynamoKnowledgeRepository:
    """
    Knowledge records in DynamoDB.

    Table schema:
    - PK: knowledge_id (String)
    """

    def __init__(self, table_name: str, region: Optional[str] = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        self._table = boto3.resource("dynamodb", region_name=self._region).Table(table_name)

    @classmethod
    def from_env(cls) -> "DynamoKnowledgeRepository":
        table_name = (os.getenv("DYNAMODB_KNOWLEDGE_TABLE") or "").strip()
        if not table_name:
            raise RuntimeError(
                "DYNAMODB_KNOWLEDGE_TABLE is not set. Create a table with PK=knowledge_id (String)."
            )
        return cls(table_name)

    def create(self, item: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso_now()
        item["created_at"] = item.get("created_at") or now
        item["updated_at"] = now
        self._table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(knowledge_id)",
        )
        return _normalize_value(item)

    def upsert(self, item: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso_now()
        item["created_at"] = item.get("created_at") or now
        item["updated_at"] = now
        self._table.put_item(Item=item)
        return _normalize_value(item)

    def get(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        resp = self._table.get_item(Key={"knowledge_id": knowledge_id})
        item = resp.get("Item")
        if not item:
            return None
        return _normalize_value(item)

    def update(self, knowledge_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get(knowledge_id)
        if not current:
            return None

        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return current

        expr_names: Dict[str, str] = {}
        expr_vals: Dict[str, Any] = {}
        sets: List[str] = []

        idx = 0
        for k, v in update_data.items():
            nk = f"#f{idx}"
            vk = f":v{idx}"
            idx += 1
            expr_names[nk] = k
            expr_vals[vk] = v
            sets.append(f"{nk} = {vk}")

        expr_names["#updated_at"] = "updated_at"
        expr_vals[":updated_at"] = _iso_now()
        sets.append("#updated_at = :updated_at")

        self._table.update_item(
            Key={"knowledge_id": knowledge_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
        return self.get(knowledge_id)

    def delete(self, knowledge_id: str) -> bool:
        current = self.get(knowledge_id)
        if not current:
            return False
        self._table.delete_item(Key={"knowledge_id": knowledge_id})
        return True

    def list(
        self,
        *,
        user_id: str | None = None,
        knowledge_type: str | None = None,
        is_active: bool | None = None,
        query: str | None = None,
        limit: int | None = 1000,
    ) -> List[Dict[str, Any]]:
        scan_kwargs: Dict[str, Any] = {}
        filt = None

        if user_id:
            filt = Attr("user_id").eq(user_id)
        if knowledge_type:
            expr = Attr("knowledge_type").eq(knowledge_type)
            filt = expr if filt is None else filt & expr
        if is_active is not None:
            expr = Attr("is_active").eq(bool(is_active))
            filt = expr if filt is None else filt & expr

        q = (query or "").strip().lower()

        if filt is not None:
            scan_kwargs["FilterExpression"] = filt

        limit_n: int | None
        if limit is None:
            limit_n = None
        else:
            try:
                limit_n = max(1, int(limit))
            except Exception:
                limit_n = None

        rows: List[Dict[str, Any]] = []
        last_key = None
        while True:
            if last_key:
                scan_kwargs["ExclusiveStartKey"] = last_key
            resp = self._table.scan(**scan_kwargs)
            items = [_normalize_value(x) for x in (resp.get("Items") or [])]
            rows.extend(items)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        if q:
            rows = [
                x
                for x in rows
                if q in str(x.get("title") or "").lower()
                or q in str(x.get("source_path") or "").lower()
                or q in str(x.get("user_id") or "").lower()
                or q in str(x.get("knowledge_id") or "").lower()
            ]

        rows.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
        if limit_n is None:
            return rows
        return rows[:limit_n]
