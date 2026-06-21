"""
pipeline/store — Vector database abstraction layer for lexiredact.

  VectorStoreBase — abstract interface all vector store implementations must satisfy.
  ChromaStore     — default ChromaDB implementation using persistent local storage
                    and cosine similarity (hnsw:space: cosine).

Custom store::

    from lexiredact.pipeline.store import VectorStoreBase

    class MyStore(VectorStoreBase):
        def upsert_batch(self, ids, vectors, metadatas): ...
        def query(self, query_vector, top_k, filters): ...
        def count(self): ...

    pipeline = LexiredactPipeline(config, store=MyStore())
"""

from lexiredact.pipeline.store.base import VectorStoreBase
from lexiredact.pipeline.store.chroma import ChromaStore

__all__ = ["VectorStoreBase", "ChromaStore"]
