"""
cache — Redis-backed embedding cache for lexiredact.

  EmbeddingCache — transparent cache layer keyed on SHA-256 of chunk text.
                   Any Redis failure is caught silently; callers never see exceptions.
                   Disabled entirely when CacheConfig.enabled=False.
"""

from lexiredact.cache.redis_cache import EmbeddingCache

__all__ = ["EmbeddingCache"]
