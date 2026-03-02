"""
Abstract cache backend interface for VectorShield.

Cache is used ONLY for PII detection results, not embeddings.
This enables fast lookup of previously processed text.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class CacheBackend(ABC):
    """Abstract interface for caching PII detection results."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to cache backend."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connection and cleanup resources."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached PII detection result.
        
        Args:
            key: Cache key (typically hash of original text)
            
        Returns:
            Cached result dict with 'clean_text' and 'pii_found' fields,
            or None if not found
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        """
        Store PII detection result in cache.
        
        Args:
            key: Cache key (typically hash of original text)
            value: Result dict containing 'clean_text' and 'pii_found'
            ttl: Time-to-live in seconds
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete cached entry.
        
        Args:
            key: Cache key to delete
        """
        pass