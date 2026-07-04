from __future__ import annotations

import pytest

from app.services.app_usage_service import AppUsageService, feature_from_path


class _FakeUsageRepo:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def put_item(self, item: dict) -> dict:
        self.items.append(item)
        return item

    def list_items(self, **kwargs):
        return list(self.items)


@pytest.mark.unit
def test_feature_from_path_maps_known_routes():
    assert feature_from_path('/api/search') == 'knowledge_explorer'
    assert feature_from_path('/api/insights/summary') == 'learning_insights'
    assert feature_from_path('/api/admin/users') == 'admin'


@pytest.mark.unit
def test_estimate_cost_uses_model_pricing():
    svc = AppUsageService(_FakeUsageRepo())

    cost = svc.estimate_cost_usd(
        'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        token_in=1000,
        token_out=2000,
    )

    expected = (1000 / 1_000_000.0) * 1.00 + (2000 / 1_000_000.0) * 5.00
    assert cost == pytest.approx(expected, rel=0, abs=1e-12)


@pytest.mark.unit
def test_record_invocation_persists_feature_tokens_and_cost():
    repo = _FakeUsageRepo()
    svc = AppUsageService(repo)

    row = svc.record_invocation(
        method='POST',
        path='/api/search',
        status_code=200,
        duration_ms=18,
        user_id='u_1',
        model_id='google.gemma-3-27b-it',
        token_in=5000,
        token_out=1000,
    )

    assert row['feature'] == 'knowledge_explorer'
    assert row['token_in'] == 5000
    assert row['token_out'] == 1000
    assert row['estimated_cost_usd'] > 0
    assert len(repo.items) == 1


@pytest.mark.unit
def test_dashboard_summary_aggregates_rows(monkeypatch: pytest.MonkeyPatch):
    svc = AppUsageService(_FakeUsageRepo())

    fake_rows = [
        {
            'usage_id': '1',
            'user_id': 'u1',
            'feature': 'knowledge_explorer',
            'token_in': 100,
            'token_out': 50,
            'estimated_cost_usd': 0.01,
            'day_bucket': '2026-04-10',
            'model_id': 'google.gemma-3-27b-it',
        },
        {
            'usage_id': '2',
            'user_id': 'u2',
            'feature': 'learning_insights',
            'token_in': 200,
            'token_out': 30,
            'estimated_cost_usd': 0.02,
            'day_bucket': '2026-04-10',
            'model_id': 'google.gemma-3-27b-it',
        },
    ]

    monkeypatch.setattr(svc, 'list_usage', lambda **kwargs: fake_rows)

    summary = svc.dashboard_summary(days=30)

    assert summary['summary']['total_requests'] == 2
    assert summary['summary']['unique_users'] == 2
    assert summary['summary']['token_in'] == 300
    assert summary['summary']['token_out'] == 80
    assert summary['summary']['estimated_cost_usd'] == pytest.approx(0.03)
    assert summary['requests_by_feature'][0]['requests'] == 1
    assert summary['model_usage'][0]['requests'] == 2
