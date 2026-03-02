"""
Generic cache wrapper for universal cache backend support.
"""
from typing import Dict, Any, Optional, Callable
import asyncio
from ...interfaces import CacheBackend


class GenericCache(CacheBackend):
    """
    Universal cache that wraps ANY cache backend.
    
    Users can integrate Redis, Memcached, or any custom cache.
    """
    
    def __init__(
        self,
        get_func: Callable[[str], Optional[Dict[str, Any]]],
        set_func: Callable[[str, Dict[str, Any], Optional[int]], None],
        connect_func: Optional[Callable[[], None]] = None,
        close_func: Optional[Callable[[], None]] = None,
        delete_func: Optional[Callable[[str], None]] = None,
        name: str = "custom"
    ):
        """
        Initialize generic cache.
        
        Args:
            get_func: Function(key: str) -> Optional[Dict]
            set_func: Function(key: str, value: Dict, ttl: int) -> None
            connect_func: Optional connection function
            close_func: Optional cleanup function
            delete_func: Optional delete function
            name: Cache name for logging
            
        Examples:
            # Redis (raw client)
            >>> import redis
            >>> import json
            >>> client = redis.Redis(host='localhost')
            >>> cache = GenericCache(
            ...     get_func=lambda k: json.loads(client.get(k)) if client.get(k) else None,
            ...     set_func=lambda k, v, ttl: client.setex(k, ttl, json.dumps(v)),
            ...     connect_func=lambda: client.ping(),
            ...     close_func=lambda: client.close(),
            ...     name="redis-custom"
            ... )
            
            # Memcached
            >>> import memcache
            >>> mc = memcache.Client(['127.0.0.1:11211'])
            >>> cache = GenericCache(
            ...     get_func=mc.get,
            ...     set_func=lambda k, v, ttl: mc.set(k, v, time=ttl),
            ...     name="memcached"
            ... )
            
            # Simple dict
            >>> cache_dict = {}
            >>> cache = GenericCache(
            ...     get_func=lambda k: cache_dict.get(k),
            ...     set_func=lambda k, v, ttl: cache_dict.update({k: v}),
            ...     name="dict"
            ... )
        """
        self.get_func = get_func
        self.set_func = set_func
        self.connect_func = connect_func
        self.close_func = close_func
        self.delete_func = delete_func or (lambda k: None)
        self.name = name
    
    async def connect(self) -> None:
        """Establish connection."""
        if self.connect_func:
            result = self.connect_func()
            if hasattr(result, '__await__'):
                await result
    
    async def close(self) -> None:
        """Close connection."""
        if self.close_func:
            result = self.close_func()
            if hasattr(result, '__await__'):
                await result
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        loop = asyncio.get_event_loop()
        result = self.get_func(key)
        if hasattr(result, '__await__'):
            return await result
        else:
            return await loop.run_in_executor(None, lambda: result)
    
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        """Set value in cache."""
        loop = asyncio.get_event_loop()
        result = self.set_func(key, value, ttl)
        if hasattr(result, '__await__'):
            await result
        else:
            await loop.run_in_executor(None, lambda: result)
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        loop = asyncio.get_event_loop()
        result = self.delete_func(key)
        if hasattr(result, '__await__'):
            await result
        else:
            await loop.run_in_executor(None, lambda: result)