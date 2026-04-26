"""Tests for IndexingJobService (Redis-backed job tracking)."""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.indexing_job_service import IndexingJobService


@pytest.fixture
def job_service():
    """Create job service with mocked Redis."""
    with patch("app.services.indexing_job_service._get_redis_client") as mock_redis_factory:
        mock_redis = MagicMock()
        mock_redis_factory.return_value = mock_redis
        service = IndexingJobService()
        service._redis = mock_redis
        return service, mock_redis


def test_create_job_success(job_service):
    """Test successful job creation."""
    service, mock_redis = job_service
    mock_redis.smembers.return_value = set()  # No active jobs
    mock_redis.scard.return_value = 0  # No global active jobs
    mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=mock_redis.pipeline.return_value)
    mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=None)
    mock_redis.pipeline.return_value.execute.return_value = None

    job_id = service.create_job(
        user_id="user123",
        job_type="index_all",
        params={"force": False, "selected_paths": []},
    )

    assert job_id is not None
    assert isinstance(job_id, str)
    assert len(job_id) == 36  # UUID format


def test_create_job_per_user_limit_hit(job_service):
    """Test that per-user concurrency limit is enforced."""
    service, mock_redis = job_service
    mock_redis.smembers.return_value = {"job1", "job2", "job3"}  # Already 3 jobs
    mock_redis.scard.return_value = 3

    job_id = service.create_job(
        user_id="user123",
        job_type="index_all",
        params={},
    )

    assert job_id is None


def test_create_job_global_limit_hit(job_service):
    """Test that global concurrency limit is enforced."""
    service, mock_redis = job_service
    mock_redis.smembers.return_value = set()
    mock_redis.scard.return_value = 20  # Already at global limit

    job_id = service.create_job(
        user_id="user123",
        job_type="index_all",
        params={},
    )

    assert job_id is None


def test_get_job_success(job_service):
    """Test fetching job metadata."""
    service, mock_redis = job_service
    mock_redis.hgetall.return_value = {
        "job_id": "test-job-id",
        "user_id": "user123",
        "job_type": "index_all",
        "status": "running",
        "progress": json.dumps({"stage": "embedding", "current": 50, "total": 100}),
        "params": json.dumps({"force": False}),
        "result": "",
        "error": "",
    }

    job = service.get_job("test-job-id")

    assert job is not None
    assert job["job_id"] == "test-job-id"
    assert job["user_id"] == "user123"
    assert job["progress"]["stage"] == "embedding"
    assert job["params"]["force"] is False


def test_get_job_not_found(job_service):
    """Test fetching non-existent job."""
    service, mock_redis = job_service
    mock_redis.hgetall.return_value = {}

    job = service.get_job("nonexistent-job-id")

    assert job is None


def test_update_job_status(job_service):
    """Test updating job status."""
    service, mock_redis = job_service
    mock_redis.hexists.return_value = False

    result = service.update_job(
        job_id="test-job-id",
        status="running",
        progress={"stage": "embedding", "current": 50, "total": 100},
    )

    assert result is True
    mock_redis.hset.assert_called_once()


def test_mark_job_completed(job_service):
    """Test marking job as completed."""
    service, mock_redis = job_service
    mock_redis.hexists.return_value = False

    result = service.mark_job_completed(
        job_id="test-job-id",
        result={"status": "ok", "chunks": 100},
    )

    assert result is True
    mock_redis.hset.assert_called_once()
    call_args = mock_redis.hset.call_args
    mapping = call_args[1].get("mapping", {})
    assert "status" in mapping and mapping["status"] == "completed"


def test_mark_job_failed(job_service):
    """Test marking job as failed."""
    service, mock_redis = job_service
    mock_redis.hexists.return_value = False

    result = service.mark_job_failed(
        job_id="test-job-id",
        error="Qdrant connection failed",
    )

    assert result is True
    mock_redis.hset.assert_called_once()
    call_args = mock_redis.hset.call_args
    mapping = call_args[1].get("mapping", {})
    assert "status" in mapping and mapping["status"] == "failed"


def test_delete_job(job_service):
    """Test deleting job record."""
    service, mock_redis = job_service
    mock_redis.hgetall.return_value = {
        "job_id": "test-job-id",
        "user_id": "user123",
    }
    mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=mock_redis.pipeline.return_value)
    mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=None)
    mock_redis.pipeline.return_value.execute.return_value = None

    result = service.delete_job("test-job-id")

    assert result is True
    mock_redis.pipeline.assert_called_once()


def test_check_concurrency_limit_under_limit(job_service):
    """Test concurrency check when under limit."""
    service, mock_redis = job_service
    mock_redis.smembers.return_value = {"job1"}  # Only 1 job

    can_proceed = service.check_concurrency_limit("user123")

    assert can_proceed is True


def test_check_concurrency_limit_at_limit(job_service):
    """Test concurrency check when at limit."""
    service, mock_redis = job_service
    mock_redis.smembers.return_value = {"job1", "job2", "job3"}  # At limit

    can_proceed = service.check_concurrency_limit("user123")

    assert can_proceed is False


def test_cleanup_job_on_completion(job_service):
    """Test removing job from active sets."""
    service, mock_redis = job_service
    mock_redis.hgetall.return_value = {
        "job_id": "test-job-id",
        "user_id": "user123",
    }
    mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=mock_redis.pipeline.return_value)
    mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=None)
    mock_redis.pipeline.return_value.execute.return_value = None

    service.cleanup_job_on_completion("test-job-id")

    mock_redis.pipeline.assert_called_once()


def test_job_json_serialization(job_service):
    """Test that JSON fields are properly serialized/deserialized."""
    service, mock_redis = job_service
    progress_dict = {"stage": "embedding", "current": 50, "total": 100}
    params_dict = {"force": False, "selected_paths": ["file1.pdf"]}

    mock_redis.hgetall.return_value = {
        "job_id": "test-job-id",
        "progress": json.dumps(progress_dict),
        "params": json.dumps(params_dict),
        "result": "",
    }

    job = service.get_job("test-job-id")

    assert isinstance(job["progress"], dict)
    assert job["progress"]["stage"] == "embedding"
    assert isinstance(job["params"], dict)
    assert job["params"]["force"] is False
