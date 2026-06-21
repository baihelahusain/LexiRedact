"""
cache/redis_cache.py — Redis-backed embedding cache.

Failure contract (critical):
  - LexiredactCacheError is raised internally but NEVER propagated to callers.
  - Any Redis error, JSON decode error, or connection failure results in a cache
    miss (get → None) or a silent no-op (set → return). The pipeline continues.
"""

from __future__ import annotations

import hashlib
import json

from lexiredact.config.schema import CacheConfig
from lexiredact.exceptions import LexiredactCacheError
from lexiredact.app_logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """Redis-backed embedding cache. Completely transparent to callers.

    When config.enabled is False, every method is a no-op and get always
    returns None. No Redis connection is attempted.

    Args:
        config: Cache configuration (redis_url, ttl_seconds, key_prefix, enabled).
    """

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._client = None  # redis.Redis instance; created lazily on first use.
        logger.debug("EmbeddingCache initialized (enabled=%s)", config.enabled)

    def get(self, text: str) -> list[float] | None:
        """Return cached embedding for text or None on any miss/error."""
        if not self._config.enabled:
            return None
        key = self._make_key(text)
        try:
            self._ensure_connected()
            raw = self._client.get(key)  # type: ignore[union-attr]
            if raw is None:
                return None
            vector: list[float] = json.loads(raw)
            if not isinstance(vector, list):
                raise LexiredactCacheError(
                    "Cached value is not a list",
                    context={"key": key, "got_type": type(vector).__name__},
                )
            return vector
        except LexiredactCacheError as exc:
            logger.warning("Cache get failed for key '%s': %s", key, exc)
            return None
        except json.JSONDecodeError as exc:
            logger.warning("Cache get: JSON decode error for key '%s': %s", key, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache get: Redis error for key '%s': %s", key, exc)
            return None

    def set(self, text: str, vector: list[float]) -> None:
        """Store embedding in Redis with configured TTL. Silent on any error."""
        if not self._config.enabled:
            return
        key = self._make_key(text)
        try:
            self._ensure_connected()
            self._client.setex(key, self._config.ttl_seconds, json.dumps(vector))  # type: ignore[union-attr]
            logger.debug("Cache set: stored %d-dim vector at key '%s'.", len(vector), key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache set failed for key '%s': %s", key, exc)

    def _make_key(self, text: str) -> str:
        """Build Redis key: {prefix}:emb:{sha256(text)[:16]}"""
        hash_fragment = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self._config.key_prefix}:emb:{hash_fragment}"

    def _ensure_connected(self) -> None:
        """Lazily initialise the Redis client. Raises LexiredactCacheError on failure."""
        if self._client is not None:
            return
        try:
            import redis  # type: ignore[import-untyped]
            self._client = redis.Redis.from_url(
                self._config.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            logger.debug("Redis client connected to %s.", self._config.redis_url)
        except Exception as exc:
            raise LexiredactCacheError(
                "Failed to initialise Redis client",
                context={"redis_url": self._config.redis_url, "error": str(exc)},
            ) from exc
