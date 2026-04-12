from __future__ import annotations

import pytest

from app.identity.user_repository_dynamo import DynamoUserRepository


class _FakeScanTable:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = 0

    def scan(self, **kwargs):
        idx = self.calls
        self.calls += 1
        if idx < len(self.pages):
            return self.pages[idx]
        return {"Items": []}


@pytest.mark.unit
def test_get_item_by_email_scans_multiple_pages():
    repo = DynamoUserRepository.__new__(DynamoUserRepository)
    repo._table = _FakeScanTable(
        [
            {"Items": [], "LastEvaluatedKey": {"uid": "p1"}},
            {"Items": [{"uid": "u1", "email": "admin@local.dev"}]},
        ]
    )

    item = repo.get_item_by_email("admin@local.dev")

    assert item is not None
    assert item["uid"] == "u1"
    assert repo._table.calls == 2


@pytest.mark.unit
def test_get_item_by_username_scans_multiple_pages():
    repo = DynamoUserRepository.__new__(DynamoUserRepository)
    repo._table = _FakeScanTable(
        [
            {"Items": [], "LastEvaluatedKey": {"uid": "p1"}},
            {"Items": [{"uid": "u2", "username": "admin"}]},
        ]
    )

    item = repo.get_item_by_username("admin")

    assert item is not None
    assert item["uid"] == "u2"
    assert repo._table.calls == 2
