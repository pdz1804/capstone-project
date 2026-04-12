from __future__ import annotations

import os
from math import isfinite
from decimal import Decimal
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Attr


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


def _to_dynamo_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_to_dynamo_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamo_value(v) for k, v in value.items()}
    if isinstance(value, float):
        # boto3 DynamoDB serializer does not accept Python float values.
        if not isfinite(value):
            return Decimal("0")
        return Decimal(str(value))
    return value


class DynamoAppUsageRepository:
    """
    App usage records in DynamoDB.

    Table schema:
    - PK: usage_id (String)
    """

    def __init__(self, table_name: str, region: Optional[str] = None) -> None:
        import boto3

        self._region = (region or os.getenv("AWS_REGION") or "us-east-1").strip()
        self._table = boto3.resource("dynamodb", region_name=self._region).Table(table_name)

    @classmethod
    def from_env(cls) -> "DynamoAppUsageRepository":
        name = (os.getenv("DYNAMODB_APP_USAGE_TABLE") or "").strip()
        if not name:
            raise RuntimeError(
                "DYNAMODB_APP_USAGE_TABLE is not set. Create a table with PK=usage_id (String)."
            )
        return cls(name)

    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        dynamo_item = _to_dynamo_value(item)
        self._table.put_item(Item=dynamo_item)
        return _normalize_value(dynamo_item)

    def get_item(self, usage_id: str) -> Optional[Dict[str, Any]]:
        resp = self._table.get_item(Key={"usage_id": usage_id})
        item = resp.get("Item")
        if not item:
            return None
        return _normalize_value(item)

    def list_items(
        self,
        *,
        user_id: str | None = None,
        feature: str | None = None,
        model_id: str | None = None,
        start_epoch: int | None = None,
        end_epoch: int | None = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        scan_kwargs: Dict[str, Any] = {}
        filt = None

        if user_id:
            filt = Attr("user_id").eq(user_id)
        if feature:
            expr = Attr("feature").eq(feature)
            filt = expr if filt is None else filt & expr
        if model_id:
            expr = Attr("model_id").eq(model_id)
            filt = expr if filt is None else filt & expr
        if start_epoch is not None:
            expr = Attr("invoked_at_epoch").gte(int(start_epoch))
            filt = expr if filt is None else filt & expr
        if end_epoch is not None:
            expr = Attr("invoked_at_epoch").lte(int(end_epoch))
            filt = expr if filt is None else filt & expr

        if filt is not None:
            scan_kwargs["FilterExpression"] = filt

        rows: List[Dict[str, Any]] = []
        last_key = None
        while True:
            if last_key:
                scan_kwargs["ExclusiveStartKey"] = last_key
            resp = self._table.scan(**scan_kwargs)
            items = resp.get("Items") or []
            rows.extend(_normalize_value(x) for x in items)
            if len(rows) >= limit:
                break
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        rows.sort(key=lambda x: int(x.get("invoked_at_epoch") or 0), reverse=True)
        return rows[:limit]
