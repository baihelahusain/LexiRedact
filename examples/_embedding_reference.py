"""Small deterministic test doubles used by the examples.

These classes are intentionally simple. They implement LexiRedact's public
extension interfaces without downloading models or starting a vector database.
"""

from __future__ import annotations

import math
from typing import Any

from lexiredact.pipeline.embedder.base import EmbedderBase
from lexiredact.pipeline.store.base import VectorStoreBase


class DeterministicEmbedder(EmbedderBase):
    """Toy embedder for examples and tests."""

    def __init__(self, dimension: int = 4) -> None:
        self._dimension = dimension

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def query_embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def get_dimension(self) -> int:
        return self._dimension

    def _embed(self, text: str) -> list[float]:
        buckets = [0.0] * self._dimension
        for index, char in enumerate(text.lower()):
            buckets[index % self._dimension] += (ord(char) % 31) / 31.0
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]


class InMemoryVectorStore(VectorStoreBase):
    """Minimal in-memory vector store with cosine-style scoring."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        for chunk_id, vector, metadata in zip(ids, vectors, metadatas):
            self.records[chunk_id] = {"vector": vector, "metadata": metadata}

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk_id, record in self.records.items():
            metadata = record["metadata"]
            if filters and any(metadata.get(key) != value for key, value in filters.items()):
                continue
            score = _dot(query_vector, record["vector"])
            rows.append({"id": chunk_id, "metadata": metadata, "distance": 1.0 - score})
        return sorted(rows, key=lambda row: row["distance"])[:top_k]

    def count(self) -> int:
        return len(self.records)


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
