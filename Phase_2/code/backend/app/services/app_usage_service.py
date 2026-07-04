from __future__ import annotations

import os
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.repositories.app_usage_repository_dynamo import DynamoAppUsageRepository


@dataclass(frozen=True)
class ModelPrice:
    model_id: str
    display_name: str
    input_price_per_million: float
    output_price_per_million: float


MODEL_PRICES: List[ModelPrice] = [
    ModelPrice(
        model_id="zai.glm-4.7",
        display_name="Z.AI GLM 4.7",
        input_price_per_million=0.60,
        output_price_per_million=2.20,
    ),
    ModelPrice(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        display_name="Claude Haiku 4.5",
        input_price_per_million=1.00,
        output_price_per_million=5.00,
    ),
    ModelPrice(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        display_name="Claude Sonnet 4",
        input_price_per_million=3.00,
        output_price_per_million=15.00,
    ),
    ModelPrice(
        model_id="us.anthropic.claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        input_price_per_million=3.30,
        output_price_per_million=16.50,
    ),
    ModelPrice(
        model_id="google.gemma-3-27b-it",
        display_name="Gemma 3 27B",
        input_price_per_million=0.23,
        output_price_per_million=0.38,
    ),
    ModelPrice(
        model_id="zai.glm-4.7-flash",
        display_name="GLM 4.7 Flash",
        input_price_per_million=0.07,
        output_price_per_million=0.40,
    ),
    ModelPrice(
        model_id="zai.glm-4.7",
        display_name="GLM 4.7",
        input_price_per_million=0.60,
        output_price_per_million=2.20,
    ),
    ModelPrice(
        model_id="zai.glm-5",
        display_name="GLM 5",
        input_price_per_million=1.00,
        output_price_per_million=3.20,
    ),
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _parse_datetime_utc(raw: str | None) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _hour_bucket_from_row(row: Dict[str, Any]) -> str | None:
    invoked_epoch = _safe_int(row.get("invoked_at_epoch"), 0)
    dt: datetime | None = None
    if invoked_epoch > 0:
        dt = datetime.fromtimestamp(invoked_epoch, tz=timezone.utc)
    else:
        dt = _parse_datetime_utc(row.get("invoked_at"))
    if dt is None:
        return None
    return dt.replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def feature_from_path(path: str) -> str:
    p = (path or "").strip().lower()
    if p.startswith("/api/search"):
        return "knowledge_explorer"
    if p.startswith("/api/insights"):
        return "learning_insights"
    if p.startswith("/api/chat"):
        return "chat_assistant"
    if p.startswith("/api/feedback"):
        return "feedback"
    if p.startswith("/api/files") or p.startswith("/api/upload") or p.startswith("/api/process") or p.startswith("/api/index"):
        return "knowledge_management"
    if p.startswith("/api/quiz"):
        return "quiz"
    if p.startswith("/api/users") or p.startswith("/api/auth"):
        return "identity"
    if p.startswith("/api/admin"):
        return "admin"
    return "system"


class AppUsageService:
    def __init__(self, repo: DynamoAppUsageRepository) -> None:
        self.repo = repo
        self._price_map: Dict[str, ModelPrice] = {x.model_id: x for x in MODEL_PRICES}

    @classmethod
    def from_env(cls) -> "AppUsageService":
        return cls(DynamoAppUsageRepository.from_env())

    @classmethod
    def from_env_optional(cls) -> "AppUsageService | None":
        try:
            return cls.from_env()
        except Exception:
            return None

    def pricing_catalog(self) -> List[Dict[str, Any]]:
        return [
            {
                "model_id": p.model_id,
                "display_name": p.display_name,
                "input_price_per_million": p.input_price_per_million,
                "output_price_per_million": p.output_price_per_million,
            }
            for p in MODEL_PRICES
        ]

    def estimate_cost_usd(self, model_id: str | None, token_in: int, token_out: int) -> float:
        if not model_id:
            return 0.0
        price = self._price_map.get(model_id)
        if not price:
            return 0.0
        in_cost = (max(token_in, 0) / 1_000_000.0) * price.input_price_per_million
        out_cost = (max(token_out, 0) / 1_000_000.0) * price.output_price_per_million
        return round(in_cost + out_cost, 8)

    def record_invocation(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        user_id: str,
        model_id: str | None = None,
        token_in: int = 0,
        token_out: int = 0,
        feature: str | None = None,
        request_id: str | None = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        model = (model_id or "").strip() or None
        feat = (feature or "").strip() or feature_from_path(path)
        token_in_n = _safe_int(token_in, 0)
        token_out_n = _safe_int(token_out, 0)

        item = {
            "usage_id": str(uuid.uuid4()),
            "request_id": request_id or "",
            "method": (method or "GET").upper(),
            "path": path,
            "feature": feat,
            "status_code": int(status_code),
            "duration_ms": max(0, int(duration_ms)),
            "user_id": user_id or "anonymous",
            "model_id": model or "",
            "token_in": token_in_n,
            "token_out": token_out_n,
            "estimated_cost_usd": self.estimate_cost_usd(model, token_in_n, token_out_n),
            "invoked_at": now.isoformat(),
            "invoked_at_epoch": int(now.timestamp()),
            "day_bucket": now.strftime("%Y-%m-%d"),
        }
        return self.repo.put_item(item)

    def list_usage(
        self,
        *,
        days: int = 30,
        user_id: str | None = None,
        feature: str | None = None,
        model_id: str | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        end = _utc_now()
        start = end - timedelta(days=max(1, min(days, 365)))
        return self.repo.list_items(
            user_id=user_id,
            feature=feature,
            model_id=model_id,
            start_epoch=int(start.timestamp()),
            end_epoch=int(end.timestamp()),
            limit=limit,
        )

    def user_usage_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        rows = self.list_usage(days=days, user_id=user_id, limit=None)
        total_requests = len(rows)
        token_in = sum(_safe_int(x.get("token_in"), 0) for x in rows)
        token_out = sum(_safe_int(x.get("token_out"), 0) for x in rows)
        cost_usd = round(sum(float(x.get("estimated_cost_usd") or 0.0) for x in rows), 6)

        by_feature: Dict[str, int] = defaultdict(int)
        for row in rows:
            by_feature[str(row.get("feature") or "system")] += 1

        return {
            "user_id": user_id,
            "days": days,
            "total_requests": total_requests,
            "token_in": token_in,
            "token_out": token_out,
            "estimated_cost_usd": cost_usd,
            "requests_by_feature": [
                {"feature": k, "requests": v}
                for k, v in sorted(by_feature.items(), key=lambda kv: kv[1], reverse=True)
            ],
        }

    def dashboard_summary(self, days: int = 30) -> Dict[str, Any]:
        rows = self.list_usage(days=days, limit=None)

        total_requests = len(rows)
        token_in = sum(_safe_int(x.get("token_in"), 0) for x in rows)
        token_out = sum(_safe_int(x.get("token_out"), 0) for x in rows)
        total_cost = round(sum(_safe_float(x.get("estimated_cost_usd"), 0.0) for x in rows), 6)
        unique_users = len({str(x.get("user_id") or "") for x in rows if str(x.get("user_id") or "")})

        by_feature: Dict[str, int] = defaultdict(int)
        by_day_requests: Dict[str, int] = defaultdict(int)
        by_day_tokens_in: Dict[str, int] = defaultdict(int)
        by_day_tokens_out: Dict[str, int] = defaultdict(int)
        by_day_users: Dict[str, set[str]] = defaultdict(set)
        by_hour_requests: Dict[str, int] = defaultdict(int)
        by_hour_tokens_in: Dict[str, int] = defaultdict(int)
        by_hour_tokens_out: Dict[str, int] = defaultdict(int)
        by_hour_users: Dict[str, set[str]] = defaultdict(set)
        by_status: Dict[str, int] = defaultdict(int)
        by_user: Dict[str, Dict[str, Any]] = {}
        by_model: Dict[str, Dict[str, Any]] = {}

        total_duration_ms = 0
        error_requests = 0
        chat_requests = 0
        feedback_requests = 0

        for row in rows:
            feature = str(row.get("feature") or "system")
            day = str(row.get("day_bucket") or "")
            hour = _hour_bucket_from_row(row)
            model_id = str(row.get("model_id") or "")
            user_id = str(row.get("user_id") or "anonymous")
            status_code = _safe_int(row.get("status_code"), 0)
            duration_ms = _safe_int(row.get("duration_ms"), 0)
            in_t = _safe_int(row.get("token_in"), 0)
            out_t = _safe_int(row.get("token_out"), 0)
            row_cost = _safe_float(row.get("estimated_cost_usd"), 0.0)

            by_feature[feature] += 1
            by_status[str(status_code)] += 1

            if status_code >= 400:
                error_requests += 1

            if feature == "chat_assistant":
                chat_requests += 1
            if feature == "feedback":
                feedback_requests += 1

            total_duration_ms += max(0, duration_ms)

            if user_id not in by_user:
                by_user[user_id] = {
                    "user_id": user_id,
                    "requests": 0,
                    "token_in": 0,
                    "token_out": 0,
                    "estimated_cost_usd": 0.0,
                }
            by_user[user_id]["requests"] += 1
            by_user[user_id]["token_in"] += in_t
            by_user[user_id]["token_out"] += out_t
            by_user[user_id]["estimated_cost_usd"] = round(
                float(by_user[user_id]["estimated_cost_usd"]) + row_cost,
                6,
            )

            if day:
                by_day_requests[day] += 1
                by_day_tokens_in[day] += in_t
                by_day_tokens_out[day] += out_t
                if user_id:
                    by_day_users[day].add(user_id)

            if hour:
                by_hour_requests[hour] += 1
                by_hour_tokens_in[hour] += in_t
                by_hour_tokens_out[hour] += out_t
                if user_id:
                    by_hour_users[hour].add(user_id)

            if model_id:
                if model_id not in by_model:
                    p = self._price_map.get(model_id)
                    by_model[model_id] = {
                        "model_id": model_id,
                        "display_name": p.display_name if p else model_id,
                        "requests": 0,
                        "token_in": 0,
                        "token_out": 0,
                        "estimated_cost_usd": 0.0,
                        "input_price_per_million": p.input_price_per_million if p else None,
                        "output_price_per_million": p.output_price_per_million if p else None,
                    }
                by_model[model_id]["requests"] += 1
                by_model[model_id]["token_in"] += in_t
                by_model[model_id]["token_out"] += out_t
                by_model[model_id]["estimated_cost_usd"] = round(
                    float(by_model[model_id]["estimated_cost_usd"]) + row_cost,
                    6,
                )

        avg_duration_ms = int(total_duration_ms / total_requests) if total_requests > 0 else 0
        error_rate = round((error_requests / total_requests) * 100.0, 2) if total_requests > 0 else 0.0
        feedback_coverage_ratio = round(feedback_requests / chat_requests, 4) if chat_requests > 0 else 0.0
        feedback_coverage_percent = round(feedback_coverage_ratio * 100.0, 2)

        return {
            "days": days,
            "summary": {
                "total_requests": total_requests,
                "unique_users": unique_users,
                "token_in": token_in,
                "token_out": token_out,
                "estimated_cost_usd": total_cost,
                "avg_duration_ms": avg_duration_ms,
                "error_requests": error_requests,
                "error_rate_percent": error_rate,
            },
            "feedback_coverage": {
                "chat_requests": chat_requests,
                "feedback_requests": feedback_requests,
                "coverage_ratio": feedback_coverage_ratio,
                "coverage_percent": feedback_coverage_percent,
            },
            "requests_by_feature": [
                {"feature": k, "requests": v}
                for k, v in sorted(by_feature.items(), key=lambda kv: kv[1], reverse=True)
            ],
            "requests_by_day": [
                {"day": k, "requests": v}
                for k, v in sorted(by_day_requests.items(), key=lambda kv: kv[0])
            ],
            "requests_by_hour": [
                {"hour": k, "requests": v}
                for k, v in sorted(by_hour_requests.items(), key=lambda kv: kv[0])
            ],
            "active_users_by_day": [
                {
                    "day": k,
                    "users": len(v),
                }
                for k, v in sorted(by_day_users.items(), key=lambda kv: kv[0])
            ],
            "active_users_by_hour": [
                {
                    "hour": k,
                    "users": len(v),
                }
                for k, v in sorted(by_hour_users.items(), key=lambda kv: kv[0])
            ],
            "tokens_by_day": [
                {
                    "day": k,
                    "token_in": by_day_tokens_in.get(k, 0),
                    "token_out": by_day_tokens_out.get(k, 0),
                }
                for k in sorted(by_day_requests.keys())
            ],
            "tokens_by_hour": [
                {
                    "hour": k,
                    "token_in": by_hour_tokens_in.get(k, 0),
                    "token_out": by_hour_tokens_out.get(k, 0),
                }
                for k in sorted(by_hour_requests.keys())
            ],
            "requests_by_status": [
                {"status_code": k, "requests": v}
                for k, v in sorted(by_status.items(), key=lambda kv: kv[0])
            ],
            "requests_by_user": sorted(by_user.values(), key=lambda x: int(x.get("requests") or 0), reverse=True),
            "model_usage": sorted(by_model.values(), key=lambda x: int(x.get("requests") or 0), reverse=True),
            "pricing_catalog": self.pricing_catalog(),
        }
