"""
Vector store implementations for LexiRedact.
"""

from .chroma import ChromaVectorStore
from .generic import GenericVectorStore  # ADD

__all__ = [
    "ChromaVectorStore",
    "GenericVectorStore",  # ADD
]