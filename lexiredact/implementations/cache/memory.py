"""
In-memory cache implementation for LexiRedact.

Default cache backend - no external dependencies required.
Thread-safe and async-compatible.
"""
from typing import Optional, Dict, Any
import asyncio
import time
from threading import Lock
from ...interfaces import CacheBackend


class MemoryCache(CacheBackend):
    """
    In-memory cache using Python dictionary.
    
    This is the default cache backend. It stores data in process memory
    and does not persist across restarts. Suitable for development and
    single-instance deployments.
    """
    
    def __init__(self):
        """Initialize in-memory cache."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    async def connect(self) -> None:
        """No connection needed for memory cache."""
        pass
    
    async def close(self) -> None:
        """Clear cache on close."""
        with self._lock:
            self._cache.clear()
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry["expires_at"] < time.time():
                del self._cache[key]
                return None
            
            return entry["value"]
    
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        with self._lock:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl
            }
    
    async def delete(self, key: str) -> None:
        """
        Delete cached value.
        
        Args:
            key: Cache key to delete
        """
        with self._lock:
            self._cache.pop(key, None)
    
    def size(self) -> int:
        """
        Get number of items in cache.
        
        Returns:
            Number of cached entries
        """
        with self._lock:
            return len(self._cache)
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        removed = 0
        
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry["expires_at"] < current_time
            ]
            
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        
        return removed