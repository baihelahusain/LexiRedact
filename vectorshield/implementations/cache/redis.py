"""
Redis cache implementation for VectorShield.

Optional high-performance cache for production deployments.
Requires: pip install redis
"""
from typing import Optional, Dict, Any
import json
from ...interfaces import CacheBackend

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache(CacheBackend):
    """
    Redis-based cache implementation.
    
    Provides persistent, distributed caching across multiple instances.
    Requires Redis server running.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "vectorshield"
    ):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            key_prefix: Prefix for all cache keys
            
        Raises:
            ImportError: If redis package is not installed
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis support requires the redis package. "
                "Install with: pip install redis"
            )
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self) -> None:
        """Establish connection to Redis."""
        self.client = aioredis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        try:
            await self.client.ping()
            print(f"✅ Redis connected at {self.host}:{self.port}")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            print("   Falling back to memory cache")
            self.client = None
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
    
    def _make_key(self, key: str) -> str:
        """Generate full Redis key with prefix."""
        return f"{self.key_prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached value from Redis.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.client:
            return None
        
        try:
            redis_key = self._make_key(key)
            data = await self.client.get(redis_key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Redis get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        """
        Store value in Redis.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        if not self.client:
            return
        
        try:
            redis_key = self._make_key(key)
            data = json.dumps(value)
            await self.client.setex(redis_key, ttl, data)
        except Exception as e:
            print(f"Redis set error: {e}")
    
    async def delete(self, key: str) -> None:
        """
        Delete cached value from Redis.
        
        Args:
            key: Cache key to delete
        """
        if not self.client:
            return
        
        try:
            redis_key = self._make_key(key)
            await self.client.delete(redis_key)
        except Exception as e:
            print(f"Redis delete error: {e}")
    
    async def clear_all(self) -> None:
        """Clear all keys with the configured prefix."""
        if not self.client:
            return
        
        try:
            pattern = f"{self.key_prefix}:*"
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
        except Exception as e:
            print(f"Redis clear error: {e}")


class NoOpCache(CacheBackend):
    """
    No-operation cache (disables caching).
    
    Used when caching is explicitly disabled in configuration.
    """
    
    async def connect(self) -> None:
        pass
    
    async def close(self) -> None:
        pass
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        return None
    
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        pass
    
    async def delete(self, key: str) -> None:
        pass