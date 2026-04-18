"""Redis-backed cache client for search and retrieval payloads."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)



def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _is_probably_private_aws_cache_endpoint(redis_url: str) -> bool:
    host = (urlparse(redis_url or "").hostname or "").strip().lower()
    return bool(host.endswith(".cache.amazonaws.com"))


def _is_running_in_aws_runtime() -> bool:
    markers = (
        "AWS_EXECUTION_ENV",
        "AWS_LAMBDA_FUNCTION_NAME",
        "ECS_CONTAINER_METADATA_URI",
        "ECS_CONTAINER_METADATA_URI_V4",
    )
    return any((os.getenv(k) or "").strip() for k in markers)


@dataclass(frozen=True)
class SearchCacheConfig:
    enabled: bool = False
    backend: str = "redis"
    ttl_seconds: int = 600
    key_prefix: str = "phase2:search:v1"
    redis_url: str = "redis://localhost:6379/0"
    redis_connect_timeout_seconds: float = 2.0
    redis_read_timeout_seconds: float = 2.0
    redis_retry_cooldown_seconds: float = 30.0
    qdrant_setup_ttl_seconds: int = 3600
    allow_private_endpoint_local: bool = False

    @staticmethod
    def from_env() -> "SearchCacheConfig":
        return SearchCacheConfig(
            enabled=_bool_env("SEARCH_CACHE_ENABLED", False),
            backend=(os.getenv("SEARCH_CACHE_BACKEND", "redis") or "redis").strip().lower(),
            ttl_seconds=max(1, int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "600") or "600")),
            key_prefix=(os.getenv("SEARCH_CACHE_KEY_PREFIX", "phase2:search:v1") or "phase2:search:v1").strip(),
            redis_url=(os.getenv("SEARCH_CACHE_REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0").strip(),
            redis_connect_timeout_seconds=float(
                os.getenv("SEARCH_CACHE_REDIS_CONNECT_TIMEOUT_SECONDS", "2") or "2"
            ),
            redis_read_timeout_seconds=float(
                os.getenv("SEARCH_CACHE_REDIS_READ_TIMEOUT_SECONDS", "2") or "2"
            ),
            redis_retry_cooldown_seconds=float(
                os.getenv("SEARCH_CACHE_REDIS_RETRY_COOLDOWN_SECONDS", "30") or "30"
            ),
            qdrant_setup_ttl_seconds=max(
                60,
                int(os.getenv("SEARCH_CACHE_QDRANT_SETUP_TTL_SECONDS", "3600") or "3600"),
            ),
            allow_private_endpoint_local=_bool_env("SEARCH_CACHE_ALLOW_PRIVATE_ENDPOINT_LOCAL", False),
        )


class SearchCacheClient:
    """Thin cache client wrapper around redis-py for deterministic search caching."""

    def __init__(self, config: Optional[SearchCacheConfig] = None):
        self.config = config or SearchCacheConfig.from_env()
        self._redis: Optional[Redis] = None
        self._lock = Lock()
        self._reported_disabled = False
        self._next_connect_retry_at = 0.0
        self._reported_unavailable = False

    def is_enabled(self) -> bool:
        return self.config.enabled and self.config.backend == "redis"

    def _redis_client(self) -> Optional[Redis]:
        if not self.is_enabled():
            if not self._reported_disabled:
                logger.info(
                    "Search cache disabled: SEARCH_CACHE_ENABLED=%s backend=%s",
                    self.config.enabled,
                    self.config.backend,
                )
                self._reported_disabled = True
            return None
        if self._redis is not None:
            return self._redis
        if time.time() < self._next_connect_retry_at:
            return None

        with self._lock:
            if self._redis is not None:
                return self._redis
            if time.time() < self._next_connect_retry_at:
                return None
            if (
                _is_probably_private_aws_cache_endpoint(self.config.redis_url)
                and not self.config.allow_private_endpoint_local
                and not _is_running_in_aws_runtime()
            ):
                # ElastiCache Serverless endpoints are VPC-private; skip local retries unless explicitly allowed.
                self._next_connect_retry_at = time.time() + max(
                    10.0,
                    float(self.config.redis_retry_cooldown_seconds),
                )
                if not self._reported_unavailable:
                    logger.warning(
                        "Search cache endpoint looks VPC-private (%s). Skipping connection outside AWS runtime; serving uncached responses.",
                        self.config.redis_url,
                    )
                    self._reported_unavailable = True
                return None
            try:
                self._redis = Redis.from_url(
                    self.config.redis_url,
                    socket_connect_timeout=self.config.redis_connect_timeout_seconds,
                    socket_timeout=self.config.redis_read_timeout_seconds,
                    retry_on_timeout=True,
                    health_check_interval=30,
                    decode_responses=False,
                )
                self._redis.ping()
                self._next_connect_retry_at = 0.0
                self._reported_unavailable = False
                logger.info("Search cache connected: backend=redis url=%s", self.config.redis_url)
            except Exception as e:
                self._next_connect_retry_at = time.time() + max(1.0, float(self.config.redis_retry_cooldown_seconds))
                if not self._reported_unavailable:
                    logger.warning(
                        "Search cache unavailable (%s); retrying connection in %.0fs while serving uncached responses",
                        e,
                        max(1.0, float(self.config.redis_retry_cooldown_seconds)),
                    )
                    self._reported_unavailable = True
                self._redis = None
            return self._redis

    def _build_key(self, user_id: str, request_payload: Dict[str, Any], namespace: str = "search") -> str:
        ns = (namespace or "search").strip().lower()
        canonical = json.dumps(
            {"namespace": ns, "user_id": user_id, "request": request_payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{self.config.key_prefix}:{digest}"

    def _build_marker_key(self, namespace: str, marker: str) -> str:
        ns = (namespace or "marker").strip().lower()
        mk = (marker or "").strip().lower()
        return f"{self.config.key_prefix}:{ns}:marker:{mk}"

    def get(
        self,
        user_id: str,
        request_payload: Dict[str, Any],
        namespace: str = "search",
    ) -> Optional[Dict[str, Any]]:
        client = self._redis_client()
        if client is None:
            return None
        key = self._build_key(user_id, request_payload, namespace=namespace)
        ns = (namespace or "search").strip().lower()
        try:
            raw = client.get(key)
            if raw is None:
                logger.info("Search cache miss: namespace=%s key=%s", ns, key)
                return None
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, dict):
                logger.info("Search cache hit: namespace=%s key=%s", ns, key)
                return payload
            logger.info("Search cache miss (non-dict payload): namespace=%s key=%s", ns, key)
            return None
        except (RedisError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Search cache read failed: %s", e)
            return None

    def set(
        self,
        user_id: str,
        request_payload: Dict[str, Any],
        result_payload: Dict[str, Any],
        namespace: str = "search",
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        client = self._redis_client()
        if client is None:
            return False
        key = self._build_key(user_id, request_payload, namespace=namespace)
        ns = (namespace or "search").strip().lower()
        ttl = max(1, int(ttl_seconds or self.config.ttl_seconds))
        try:
            body = json.dumps(result_payload, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
            client.setex(key, ttl, body)
            logger.info("Search cache write success: namespace=%s key=%s ttl=%ss", ns, key, ttl)
            return True
        except (RedisError, TypeError, ValueError) as e:
            logger.warning("Search cache write failed: %s", e)
            return False

    def marker_exists(self, marker: str, namespace: str = "qdrant_setup") -> bool:
        client = self._redis_client()
        if client is None:
            return False
        key = self._build_marker_key(namespace, marker)
        try:
            return bool(client.exists(key))
        except RedisError as e:
            logger.warning("Search cache marker exists check failed: %s", e)
            return False

    def set_marker(
        self,
        marker: str,
        namespace: str = "qdrant_setup",
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        client = self._redis_client()
        if client is None:
            return False
        key = self._build_marker_key(namespace, marker)
        ttl = max(60, int(ttl_seconds or self.config.qdrant_setup_ttl_seconds))
        try:
            client.setex(key, ttl, b"1")
            return True
        except RedisError as e:
            logger.warning("Search cache marker write failed: %s", e)
            return False


_CACHE: Optional[SearchCacheClient] = None
_CACHE_LOCK = Lock()



def get_search_cache_client() -> SearchCacheClient:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    with _CACHE_LOCK:
        if _CACHE is None:
            _CACHE = SearchCacheClient()
    return _CACHE
