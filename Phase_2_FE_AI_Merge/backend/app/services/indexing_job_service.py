"""
Redis-backed job tracking service for async indexing operations.
Manages job lifecycle, concurrency limits, and progress updates.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r, using default=%d", name, raw, default)
        return default


def _get_redis_client(redis_url: str = None) -> redis.Redis:
    """Get or create Redis client with optional URL override."""
    try:
        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        logger.info("Connecting to Redis: %s", url.split("@")[-1] if "@" in url else url)
        return redis.from_url(url, decode_responses=True)
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise


class IndexingJobService:
    """Manages indexing job lifecycle using Redis.

    Supports configuration-driven limits and fallback behavior.
    """

    def __init__(self, config=None):
        """Initialize job service with optional config.

        Args:
            config: RuntimeSettings object with async_indexing config, or None to use defaults
        """
        self.config = config
        self.enabled = _env_bool("ASYNC_INDEXING_ENABLED", True)
        self.max_per_user = _env_int("ASYNC_INDEXING_MAX_PER_USER", 3)
        self.max_global = _env_int("ASYNC_INDEXING_MAX_GLOBAL", 200)
        self.job_ttl = _env_int("ASYNC_INDEXING_JOB_TTL_SECONDS", 3600)
        self.fallback_to_blocking = _env_bool("ASYNC_INDEXING_FALLBACK_TO_BLOCKING", False)
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.dynamo_jobs_table = os.getenv("DYNAMODB_JOBS_TABLE", "bk_mind_app_jobs").strip()
        self.aws_region = (os.getenv("AWS_REGION") or "us-east-1").strip()

        # Load from config if provided (dict or object), then allow env override.
        async_cfg = None
        if isinstance(config, dict):
            async_cfg = config.get("async_indexing")
        elif config and hasattr(config, "async_indexing"):
            async_cfg = getattr(config, "async_indexing")

        if isinstance(async_cfg, dict):
            self.enabled = bool(async_cfg.get("enabled", self.enabled))
            self.max_per_user = int(async_cfg.get("max_concurrent_per_user", self.max_per_user))
            self.max_global = int(async_cfg.get("max_concurrent_global", self.max_global))
            self.job_ttl = int(async_cfg.get("job_ttl_seconds", self.job_ttl))
            self.fallback_to_blocking = bool(async_cfg.get("fallback_to_blocking", self.fallback_to_blocking))
            self.redis_url = str(async_cfg.get("redis_url", self.redis_url) or self.redis_url)
        elif async_cfg is not None:
            self.enabled = getattr(async_cfg, "enabled", self.enabled)
            self.max_per_user = getattr(async_cfg, "max_concurrent_per_user", self.max_per_user)
            self.max_global = getattr(async_cfg, "max_concurrent_global", self.max_global)
            self.job_ttl = getattr(async_cfg, "job_ttl_seconds", self.job_ttl)
            self.fallback_to_blocking = getattr(async_cfg, "fallback_to_blocking", self.fallback_to_blocking)
            self.redis_url = getattr(async_cfg, "redis_url", self.redis_url)

        # Env always wins in deployment.
        self.enabled = _env_bool("ASYNC_INDEXING_ENABLED", bool(self.enabled))
        self.max_per_user = _env_int("ASYNC_INDEXING_MAX_PER_USER", int(self.max_per_user))
        self.max_global = _env_int("ASYNC_INDEXING_MAX_GLOBAL", int(self.max_global))
        self.job_ttl = _env_int("ASYNC_INDEXING_JOB_TTL_SECONDS", int(self.job_ttl))
        self.fallback_to_blocking = _env_bool("ASYNC_INDEXING_FALLBACK_TO_BLOCKING", bool(self.fallback_to_blocking))
        self.redis_url = os.getenv("REDIS_URL", self.redis_url)

        logger.info(
            "IndexingJobService initialized: enabled=%s, "
            "max_per_user=%d, max_global=%d, fallback=%s",
            self.enabled,
            self.max_per_user,
            self.max_global,
            self.fallback_to_blocking,
        )

        self._redis = None
        self._dynamo_table = None
        self._prefix = "phase2:index"
        self._init_redis()
        self._init_dynamodb()

    @staticmethod
    def _to_dynamo_value(value: Any) -> Any:
        if isinstance(value, list):
            return [IndexingJobService._to_dynamo_value(v) for v in value]
        if isinstance(value, dict):
            return {k: IndexingJobService._to_dynamo_value(v) for k, v in value.items()}
        if isinstance(value, float):
            return Decimal(str(value))
        return value

    def _init_dynamodb(self) -> None:
        """Initialize DynamoDB table for durable job persistence."""
        if not self.dynamo_jobs_table:
            logger.info("DynamoDB jobs table is empty, durable job persistence disabled")
            return
        try:
            import boto3

            resource = boto3.resource("dynamodb", region_name=self.aws_region)
            self._dynamo_table = resource.Table(self.dynamo_jobs_table)
            logger.info(
                "DynamoDB job persistence enabled: table=%s region=%s",
                self.dynamo_jobs_table,
                self.aws_region,
            )
        except Exception as e:
            self._dynamo_table = None
            logger.warning("DynamoDB jobs persistence unavailable: %s", e)

    def _upsert_job_dynamo(self, payload: Dict[str, Any]) -> None:
        """Persist job snapshot to DynamoDB (best effort, non-blocking)."""
        if not self._dynamo_table:
            return
        try:
            item = dict(payload)
            item["updated_at"] = str(int(datetime.utcnow().timestamp()))
            self._dynamo_table.put_item(Item=self._to_dynamo_value(item))
        except Exception as e:
            logger.warning("Failed to persist job to DynamoDB job_id=%s: %s", payload.get("job_id"), e)

    def _sync_job_to_dynamo(self, job_id: str) -> None:
        """Sync current Redis job snapshot to DynamoDB (best effort)."""
        if not self._dynamo_table or not job_id:
            return
        try:
            job = self.get_job(job_id)
            if not job:
                return
            self._upsert_job_dynamo(job)
        except Exception as e:
            logger.warning("Failed to sync job snapshot to DynamoDB job_id=%s: %s", job_id, e)

    def _init_redis(self):
        """Initialize Redis connection with fallback handling."""
        if not self.enabled:
            logger.info("Async indexing disabled - Redis not needed")
            return

        try:
            self._redis = _get_redis_client(self.redis_url)
            # Test connection
            self._redis.ping()
            logger.info("Redis connection successful")
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            if not self.fallback_to_blocking:
                raise
            logger.warning("Redis unavailable - fallback mode enabled")

    def create_job(
        self,
        user_id: str,
        job_type: str,
        params: Dict[str, Any],
    ) -> Optional[str]:
        """
        Create a new indexing job.

        Args:
            user_id: User identifier
            job_type: "index_all", "index_text", "index_images", "process", or "remove"
            params: Job parameters (selected_paths, selected_names, force, mode, etc.)

        Returns:
            job_id (UUID string) if successful, None if concurrency limit hit or system disabled
        """
        if not self.enabled:
            logger.debug("Async indexing disabled, creating dummy job")
            return self._create_dummy_job(user_id, job_type, params)

        try:
            if not self._redis:
                raise redis.ConnectionError("Redis client not initialized")

            # Check per-user concurrency limit
            active_key = f"{self._prefix}:active:{user_id}"
            active_jobs = self._redis.smembers(active_key)
            if len(active_jobs) >= self.max_per_user:
                logger.warning(
                    "Per-user concurrency limit hit for user=%s (active=%d, max=%d)",
                    user_id,
                    len(active_jobs),
                    self.max_per_user,
                )
                return None

            # Check global concurrency limit
            global_active_key = f"{self._prefix}:global_active"
            total_active = self._redis.scard(global_active_key)
            if total_active >= self.max_global:
                logger.warning(
                    "Global concurrency limit hit (active=%d, max=%d)",
                    total_active,
                    self.max_global,
                )
                return None

            # Create job record
            job_id = str(uuid.uuid4())
            job_key = f"{self._prefix}:job:{job_id}"
            now_ts = datetime.utcnow().timestamp()

            job_data = {
                "job_id": job_id,
                "user_id": user_id,
                "job_type": job_type,
                "status": "accepted",
                "progress": json.dumps({"stage": "queued", "current": 0, "total": 0}),
                "params": json.dumps(params),
                "result": "",
                "error": "",
                "created_at": str(int(now_ts)),
                "started_at": "",
                "completed_at": "",
            }

            # Redis Cluster cannot execute MULTI/EXEC across different hash slots.
            # Use a non-transactional pipeline to avoid CROSSSLOT failures.
            pipe = self._redis.pipeline(transaction=False)
            pipe.hset(job_key, mapping=job_data)
            pipe.expire(job_key, self.job_ttl)
            pipe.sadd(active_key, job_id)
            pipe.expire(active_key, self.job_ttl)
            pipe.sadd(global_active_key, job_id)
            pipe.expire(global_active_key, self.job_ttl)
            pipe.execute()

            logger.info("Created job job_id=%s user_id=%s job_type=%s", job_id, user_id, job_type)
            self._upsert_job_dynamo(job_data)
            return job_id

        except redis.ConnectionError as e:
            logger.error("Redis connection error while creating job: %s", e)
            if self.fallback_to_blocking:
                logger.info("Falling back to blocking mode (Redis unavailable)")
                return self._create_dummy_job(user_id, job_type, params)
            logger.error("Fallback disabled - job creation failed")
            raise
        except Exception as e:
            logger.exception("Failed to create job: %s", e)
            return None

    def _create_dummy_job(self, user_id: str, job_type: str, params: Dict) -> str:
        """Create a dummy job when async is disabled or Redis unavailable."""
        job_id = str(uuid.uuid4())
        logger.info(
            "Created dummy job (fallback/disabled) job_id=%s user_id=%s job_type=%s",
            job_id,
            user_id,
            job_type,
        )
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full job metadata by job_id."""
        if not self.enabled or not self._redis:
            logger.debug("Job system disabled or Redis unavailable - returning None")
            return None

        try:
            job_key = f"{self._prefix}:job:{job_id}"
            data = self._redis.hgetall(job_key)
            if not data:
                return None

            # Parse JSON fields
            try:
                data["progress"] = json.loads(data.get("progress", "{}"))
                data["params"] = json.loads(data.get("params", "{}"))
                if data.get("result"):
                    data["result"] = json.loads(data["result"])
            except json.JSONDecodeError:
                pass

            return data
        except Exception as e:
            logger.exception("Failed to get job job_id=%s: %s", job_id, e)
            return None

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update job status and/or progress."""
        try:
            job_key = f"{self._prefix}:job:{job_id}"
            updates = {}

            if status:
                updates["status"] = status
                if status == "running":
                    started_at_raw = ""
                    try:
                        started_at_raw = str(self._redis.hget(job_key, "started_at") or "").strip()
                    except Exception:
                        started_at_raw = ""
                    # Set started_at on first transition to running (also fixes existing rows with empty started_at)
                    if not started_at_raw:
                        updates["started_at"] = str(int(datetime.utcnow().timestamp()))
                if status in ("completed", "failed"):
                    updates["completed_at"] = str(int(datetime.utcnow().timestamp()))

            if progress is not None:
                updates["progress"] = json.dumps(progress)

            if result is not None:
                updates["result"] = json.dumps(result)

            if error:
                updates["error"] = error

            if updates:
                self._redis.hset(job_key, mapping=updates)
                self._redis.expire(job_key, self.job_ttl)
                self._sync_job_to_dynamo(job_id)

            return True
        except Exception as e:
            logger.exception("Failed to update job job_id=%s: %s", job_id, e)
            return False

    def mark_job_completed(self, job_id: str, result: Dict[str, Any]) -> bool:
        """Mark job as completed with result."""
        return self.update_job(job_id, status="completed", result=result)

    def mark_job_failed(self, job_id: str, error: str) -> bool:
        """Mark job as failed with error message."""
        return self.update_job(job_id, status="failed", error=error)

    def delete_job(self, job_id: str) -> bool:
        """Delete job record and remove from active sets."""
        try:
            job = self.get_job(job_id)
            if not job:
                return True

            user_id = job.get("user_id")
            job_key = f"{self._prefix}:job:{job_id}"
            active_key = f"{self._prefix}:active:{user_id}"
            global_active_key = f"{self._prefix}:global_active"

            pipe = self._redis.pipeline(transaction=False)
            pipe.delete(job_key)
            pipe.srem(active_key, job_id)
            pipe.srem(global_active_key, job_id)
            pipe.execute()

            logger.info("Deleted job job_id=%s user_id=%s", job_id, user_id)
            return True
        except Exception as e:
            logger.exception("Failed to delete job job_id=%s: %s", job_id, e)
            return False

    def check_concurrency_limit(self, user_id: str) -> bool:
        """Check if user can start a new indexing job."""
        try:
            active_key = f"{self._prefix}:active:{user_id}"
            active_jobs = self._redis.smembers(active_key)
            return len(active_jobs) < self.max_per_user
        except Exception as e:
            logger.warning("Failed to check concurrency limit for user=%s: %s", user_id, e)
            return True  # Fail open (allow job to proceed if Redis is unavailable)

    def cleanup_job_on_completion(self, job_id: str) -> None:
        """Remove job from active sets after completion."""
        try:
            job = self.get_job(job_id)
            if job:
                user_id = job.get("user_id")
                active_key = f"{self._prefix}:active:{user_id}"
                global_active_key = f"{self._prefix}:global_active"
                pipe = self._redis.pipeline(transaction=False)
                pipe.srem(active_key, job_id)
                pipe.srem(global_active_key, job_id)
                pipe.execute()
                logger.info("Cleaned up job job_id=%s from active sets", job_id)
        except Exception as e:
            logger.warning("Failed to cleanup job job_id=%s: %s", job_id, e)
