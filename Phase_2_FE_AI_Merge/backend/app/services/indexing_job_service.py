"""
Redis-backed job tracking service for async indexing operations.
Manages job lifecycle, concurrency limits, and progress updates.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_JOBS_PER_USER = 3
MAX_CONCURRENT_JOBS_GLOBAL = 20
JOB_TTL_SECONDS = 3600  # 1 hour


def _get_redis_client() -> redis.Redis:
    """Get or create Redis client. Uses default localhost:6379."""
    try:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise


class IndexingJobService:
    """Manages indexing job lifecycle using Redis."""

    def __init__(self):
        self._redis = _get_redis_client()
        self._prefix = "phase2:index"

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
            job_id (UUID string) if successful, None if concurrency limit hit
        """
        try:
            # Check per-user concurrency limit
            active_key = f"{self._prefix}:active:{user_id}"
            active_jobs = self._redis.smembers(active_key)
            if len(active_jobs) >= MAX_CONCURRENT_JOBS_PER_USER:
                logger.warning(
                    "Per-user concurrency limit hit for user=%s (active=%d, max=%d)",
                    user_id,
                    len(active_jobs),
                    MAX_CONCURRENT_JOBS_PER_USER,
                )
                return None

            # Check global concurrency limit
            global_active_key = f"{self._prefix}:global_active"
            total_active = self._redis.scard(global_active_key)
            if total_active >= MAX_CONCURRENT_JOBS_GLOBAL:
                logger.warning(
                    "Global concurrency limit hit (active=%d, max=%d)",
                    total_active,
                    MAX_CONCURRENT_JOBS_GLOBAL,
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

            pipe = self._redis.pipeline()
            pipe.hset(job_key, mapping=job_data)
            pipe.expire(job_key, JOB_TTL_SECONDS)
            pipe.sadd(active_key, job_id)
            pipe.expire(active_key, JOB_TTL_SECONDS)
            pipe.sadd(global_active_key, job_id)
            pipe.expire(global_active_key, JOB_TTL_SECONDS)
            pipe.execute()

            logger.info("Created job job_id=%s user_id=%s job_type=%s", job_id, user_id, job_type)
            return job_id
        except Exception as e:
            logger.exception("Failed to create job: %s", e)
            return None

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full job metadata by job_id."""
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
                if status == "running" and not self._redis.hexists(job_key, "started_at"):
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
                self._redis.expire(job_key, JOB_TTL_SECONDS)

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

            pipe = self._redis.pipeline()
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
            return len(active_jobs) < MAX_CONCURRENT_JOBS_PER_USER
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
                pipe = self._redis.pipeline()
                pipe.srem(active_key, job_id)
                pipe.srem(global_active_key, job_id)
                pipe.execute()
                logger.info("Cleaned up job job_id=%s from active sets", job_id)
        except Exception as e:
            logger.warning("Failed to cleanup job job_id=%s: %s", job_id, e)
