"""
Utility functions for LexiRedact.

Provides hashing, timing, and helper functions.
"""

from .hashing import hash_text, hash_batch, generate_cache_key
from .timing import Timer, measure_time, MovingAverage

__all__ = [
    "hash_text",
    "hash_batch",
    "generate_cache_key",
    "Timer",
    "measure_time",
    "MovingAverage",
]