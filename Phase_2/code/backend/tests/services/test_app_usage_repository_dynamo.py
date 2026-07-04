from __future__ import annotations

from decimal import Decimal

import pytest

from app.repositories.app_usage_repository_dynamo import DynamoAppUsageRepository


class _FakeTable:
    def __init__(self) -> None:
        self.written_item = None

    def put_item(self, **kwargs):
        self.written_item = kwargs.get("Item")
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


@pytest.mark.unit
def test_put_item_converts_float_values_to_decimal():
    repo = DynamoAppUsageRepository.__new__(DynamoAppUsageRepository)
    repo._table = _FakeTable()

    item = {
        "usage_id": "u-1",
        "estimated_cost_usd": 0.0125,
        "nested": {"score": 1.25},
        "arr": [2.5, 1],
    }

    out = repo.put_item(item)

    assert repo._table.written_item is not None
    assert isinstance(repo._table.written_item["estimated_cost_usd"], Decimal)
    assert isinstance(repo._table.written_item["nested"]["score"], Decimal)
    assert isinstance(repo._table.written_item["arr"][0], Decimal)

    assert out["estimated_cost_usd"] == pytest.approx(0.0125)
    assert out["nested"]["score"] == pytest.approx(1.25)
    assert out["arr"][0] == pytest.approx(2.5)
