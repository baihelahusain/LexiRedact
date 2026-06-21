"""
pipeline/store/base.py — Abstract base class for all Lexiredact vector store backends.

No external library imports. Zero heavyweight dependencies.

Failure contract: upsert_batch MUST raise LexiredactStorageError on any failure.
The orchestrator does not catch storage errors — they bubble to the caller so that
data loss is never silent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VectorStoreBase(ABC):
    """Abstract interface for vector database backends.

    All three methods must raise LexiredactStorageError on failure.
    upsert_batch is idempotent: same id overwrites the previous entry.
    """

    @abstractmethod
    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Write batch of (id, vector, metadata) tuples. Idempotent by id.

        metadatas must contain "text" key with sanitised (never original) text.

        Raises:
            LexiredactStorageError: On any write failure. Never swallowed.
        """
        ...

    @abstractmethod
    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve top_k nearest results as [{"id": ..., "metadata": ..., "distance": ...}].

        Raises:
            LexiredactStorageError: On any query failure.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Return total document count.

        Raises:
            LexiredactStorageError: On any failure.
        """
        ...
