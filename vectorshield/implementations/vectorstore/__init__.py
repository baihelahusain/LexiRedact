"""
Vector store implementations for VectorShield.
"""

from .chroma import ChromaVectorStore
from .generic import GenericVectorStore  # ADD

__all__ = [
    "ChromaVectorStore",
    "GenericVectorStore",  # ADD
]