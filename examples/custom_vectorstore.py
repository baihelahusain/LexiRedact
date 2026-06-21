"""Use a custom vector store with LexiredactPipeline."""

from __future__ import annotations

from typing import Any

from _bootstrap import ROOT  # noqa: F401
from _embedding_reference import DeterministicEmbedder

from lexiredact import LexiredactPipeline, load_config
from lexiredact.pipeline.store.base import VectorStoreBase


class AuditedVectorStore(VectorStoreBase):
    """Example store that records every upsert call."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.audit_log: list[str] = []

    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.audit_log.append(f"upserted {len(ids)} records")
        for chunk_id, vector, metadata in zip(ids, vectors, metadatas):
            self.records[chunk_id] = {"vector": vector, "metadata": metadata}

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {"id": chunk_id, "metadata": record["metadata"], "distance": 0.0}
            for chunk_id, record in list(self.records.items())[:top_k]
        ]

    def count(self) -> int:
        return len(self.records)


config = load_config(
    {
        "pipeline_mode": "raw",
        "embedder": {"dimension": 4},
        "store": {"collection_name": "custom_store_demo"},
    }
)

store = AuditedVectorStore()
pipeline = LexiredactPipeline(
    config,
    embedder=DeterministicEmbedder(dimension=4),
    store=store,
)

pipeline.ingest([{"id": "doc-1", "text": "This record is written to a custom store."}])

print(store.audit_log)
print(store.records)
