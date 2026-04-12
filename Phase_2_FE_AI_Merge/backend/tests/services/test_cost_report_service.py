from __future__ import annotations

import pytest

from app.services.cost_report_service import CostReportService


class _FakeBody:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> bytes:
        return self._text.encode("utf-8")


class _FakePaginator:
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys

    def paginate(self, **kwargs):
        yield {
            "Contents": [{"Key": k} for k in self._keys],
        }


class _FakeS3:
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return _FakePaginator(list(self._objects.keys()))

    def get_object(self, *, Bucket: str, Key: str):
        assert Bucket == "bkmind-learning-platform-cost-bucket"
        return {"Body": _FakeBody(self._objects[Key])}


@pytest.mark.unit
def test_dashboard_summary_aggregates_daily_and_service_costs():
    objects = {
        "detailed/2026-04-10-usage-breakdown.csv": (
            "Service,Usage Type,Cost (USD)\n"
            "Amazon Elastic Container Service,USW2-Fargate-vCPU-Hours:perCPU,1.19\n"
            "AmazonCloudWatch,USW2-CW:MetricMonitorUsage,0.55\n"
        ),
        "detailed/2026-04-11-usage-breakdown.csv": (
            "Service,Usage Type,Cost (USD)\n"
            "Amazon Elastic Container Service,USW2-Fargate-GB-Hours,0.47\n"
            "Amazon Elastic Load Balancing,USW2-LoadBalancerUsage,0.52\n"
        ),
    }
    svc = CostReportService(
        bucket="bkmind-learning-platform-cost-bucket",
        prefix="detailed/",
        s3_client=_FakeS3(objects),
    )

    out = svc.dashboard_summary(days=7)

    assert out["summary"]["latest_day"] == "2026-04-11"
    assert out["summary"]["total_cost_usd"] == pytest.approx(2.73)
    assert len(out["cost_by_day"]) == 2
    assert out["cost_by_day"][0]["day"] == "2026-04-10"
    assert out["cost_by_day"][1]["day"] == "2026-04-11"
    assert out["cost_by_service"][0]["service"] == "Amazon Elastic Container Service"
    assert out["cost_by_service"][0]["cost_usd"] == pytest.approx(1.66)


@pytest.mark.unit
def test_dashboard_summary_supports_service_filter():
    objects = {
        "detailed/2026-04-11-usage-breakdown.csv": (
            "Service,Usage Type,Cost (USD)\n"
            "Amazon Elastic Container Service,USW2-Fargate-vCPU-Hours:perCPU,1.19\n"
            "AmazonCloudWatch,USW2-CW:MetricMonitorUsage,0.55\n"
        ),
    }
    svc = CostReportService(
        bucket="bkmind-learning-platform-cost-bucket",
        prefix="detailed/",
        s3_client=_FakeS3(objects),
    )

    out = svc.dashboard_summary(days=30, service_filter="AmazonCloudWatch")

    assert out["summary"]["total_cost_usd"] == pytest.approx(0.55)
    assert len(out["cost_by_service"]) == 1
    assert out["cost_by_service"][0]["service"] == "AmazonCloudWatch"
