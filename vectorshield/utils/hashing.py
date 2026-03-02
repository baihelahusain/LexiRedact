"""
Hashing utilities for VectorShield.

Generates deterministic cache keys from text content.
"""
import hashlib
from typing import Union


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """
    Generate a hash from text for cache key generation.
    
    Args:
        text: Input text to hash
        algorithm: Hash algorithm (default: sha256)
        
    Returns:
        Hexadecimal hash string
        
    Example:
        >>> hash_text("Hello world")
        '64ec88ca00b268e5ba1a35678a1b5316d212f4f366b2477232534a8aeca37f3c'
    """
    hasher = hashlib.new(algorithm)
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()


def hash_batch(texts: list[str], algorithm: str = "sha256") -> list[str]:
    """
    Generate hashes for multiple texts.
    
    Args:
        texts: List of input texts
        algorithm: Hash algorithm
        
    Returns:
        List of hash strings
    """
    return [hash_text(text, algorithm) for text in texts]


def generate_cache_key(text: str, prefix: str = "pii") -> str:
    """
    Generate a cache key for text.
    
    Args:
        text: Input text
        prefix: Key prefix (default: "pii")
        
    Returns:
        Cache key string
        
    Example:
        >>> generate_cache_key("Hello world")
        'pii:64ec88ca00b268e5ba1a35678a1b5316d212f4f366b2477232534a8aeca37f3c'
    """
    text_hash = hash_text(text)
    return f"{prefix}:{text_hash}"