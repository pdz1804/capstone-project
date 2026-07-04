from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from io import StringIO
from typing import Any, Dict, List, Optional

import boto3

_CSV_KEY_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})-usage-breakdown\.csv$")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


class CostReportService:
    def __init__(self, bucket: str, prefix: str = "detailed/", s3_client: Any | None = None) -> None:
        if not bucket:
            raise ValueError("Cost report bucket is required")
        self.bucket = bucket
        self.prefix = (prefix or "detailed/").strip().lstrip("/")
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"
        self._s3 = s3_client or boto3.client("s3")

    @classmethod
    def from_env_optional(cls) -> "CostReportService | None":
        bucket = (
            os.getenv("AWS_COST_REPORT_S3_BUCKET")
            or os.getenv("COST_REPORT_BUCKET")
            or ""
        ).strip()
        if not bucket:
            return None
        prefix = (
            os.getenv("AWS_COST_REPORT_S3_PREFIX")
            or os.getenv("COST_REPORT_PREFIX")
            or "detailed/"
        ).strip()
        return cls(bucket=bucket, prefix=prefix)

    @staticmethod
    def empty_dashboard(days: int, *, bucket: str = "", prefix: str = "detailed/", error: str | None = None) -> Dict[str, Any]:
        return {
            "days": max(1, min(days, 365)),
            "bucket": bucket,
            "prefix": prefix,
            "summary": {
                "total_cost_usd": 0.0,
                "avg_daily_cost_usd": 0.0,
                "services_count": 0,
                "records_count": 0,
                "latest_day": None,
                "latest_day_total_cost_usd": 0.0,
                "parse_errors": 0,
            },
            "cost_by_day": [],
            "cost_by_service": [],
            "cost_by_day_service": [],
            "latest_day_breakdown": [],
            "service_options": [],
            "error": error,
        }

    def _list_report_keys(self) -> Dict[date, str]:
        by_day: Dict[date, str] = {}
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []) or []:
                key = str(obj.get("Key") or "")
                m = _CSV_KEY_PATTERN.search(key)
                if not m:
                    continue
                try:
                    d = date.fromisoformat(m.group(1))
                except Exception:
                    continue
                by_day[d] = key
        return by_day

    def _read_rows(self, day: date, key: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        res = self._s3.get_object(Bucket=self.bucket, Key=key)
        raw = res.get("Body").read().decode("utf-8", errors="replace")
        reader = csv.DictReader(StringIO(raw))
        for row in reader:
            service = str(row.get("Service") or "").strip() or "Unknown Service"
            usage_type = str(row.get("Usage Type") or "").strip() or "Unknown Usage Type"
            amount = _safe_float(row.get("Cost (USD)") or row.get("Cost") or row.get("Amount"), 0.0)
            if amount <= 0:
                continue
            out.append(
                {
                    "day": day.isoformat(),
                    "service": service,
                    "usage_type": usage_type,
                    "cost_usd": round(amount, 6),
                }
            )
        return out

    def dashboard_summary(self, *, days: int = 30, service_filter: Optional[str] = None) -> Dict[str, Any]:
        lookback = max(1, min(days, 365))
        by_day_key = self._list_report_keys()
        if not by_day_key:
            return self.empty_dashboard(lookback, bucket=self.bucket, prefix=self.prefix)

        latest_day = max(by_day_key.keys())
        start_day = latest_day - timedelta(days=lookback - 1)
        selected_days = [d for d in sorted(by_day_key.keys()) if start_day <= d <= latest_day]

        rows: List[Dict[str, Any]] = []
        parse_errors = 0
        for d in selected_days:
            key = by_day_key[d]
            try:
                rows.extend(self._read_rows(d, key))
            except Exception:
                parse_errors += 1

        service_filter = (service_filter or "").strip()
        if service_filter:
            rows = [r for r in rows if str(r.get("service") or "") == service_filter]

        by_day_total: Dict[str, float] = defaultdict(float)
        by_service_total: Dict[str, float] = defaultdict(float)
        by_day_service: Dict[tuple[str, str], float] = defaultdict(float)

        for row in rows:
            day_s = str(row.get("day") or "")
            service = str(row.get("service") or "Unknown Service")
            amount = _safe_float(row.get("cost_usd"), 0.0)
            if not day_s:
                continue
            by_day_total[day_s] += amount
            by_service_total[service] += amount
            by_day_service[(day_s, service)] += amount

        cost_by_day = [
            {
                "day": d.isoformat(),
                "total_cost_usd": round(by_day_total.get(d.isoformat(), 0.0), 6),
            }
            for d in selected_days
        ]

        cost_by_service = [
            {"service": svc, "cost_usd": round(cost, 6)}
            for svc, cost in sorted(by_service_total.items(), key=lambda kv: kv[1], reverse=True)
        ]

        cost_by_day_service = [
            {
                "day": day_s,
                "service": svc,
                "cost_usd": round(cost, 6),
            }
            for (day_s, svc), cost in sorted(
                by_day_service.items(),
                key=lambda kv: (kv[0][0], -kv[1]),
            )
        ]

        latest_day_s = latest_day.isoformat()
        latest_day_breakdown = [
            {
                "service": str(r.get("service") or "Unknown Service"),
                "usage_type": str(r.get("usage_type") or "Unknown Usage Type"),
                "cost_usd": round(_safe_float(r.get("cost_usd"), 0.0), 6),
            }
            for r in rows
            if str(r.get("day") or "") == latest_day_s
        ]
        latest_day_breakdown.sort(key=lambda x: x["cost_usd"], reverse=True)

        total_cost = round(sum(x["total_cost_usd"] for x in cost_by_day), 6)
        avg_daily = round(total_cost / max(1, len(cost_by_day)), 6)

        return {
            "days": lookback,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "summary": {
                "total_cost_usd": total_cost,
                "avg_daily_cost_usd": avg_daily,
                "services_count": len(cost_by_service),
                "records_count": len(rows),
                "latest_day": latest_day_s,
                "latest_day_total_cost_usd": round(by_day_total.get(latest_day_s, 0.0), 6),
                "parse_errors": parse_errors,
            },
            "cost_by_day": cost_by_day,
            "cost_by_service": cost_by_service,
            "cost_by_day_service": cost_by_day_service,
            "latest_day_breakdown": latest_day_breakdown[:20],
            "service_options": [x["service"] for x in cost_by_service],
            "error": None,
        }
