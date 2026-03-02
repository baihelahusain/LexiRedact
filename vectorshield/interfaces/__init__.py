"""
VectorShield Interface Layer

Abstract base classes defining contracts for pluggable components.
Users can implement these interfaces to provide custom backends.
"""

from .cache import CacheBackend
from .embedder import Embedder
from .vectorstore import VectorStore
from .tracker import Tracker

__all__ = [
    "CacheBackend",
    "Embedder",
    "VectorStore",
    "Tracker",
]