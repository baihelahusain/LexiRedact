"""
Custom Vector Store Example

Reference example for plugging a custom storage backend into LexiRedact.

Use this file for the smallest possible adapter pattern.
Use `custom_vectordb_comparison.py` when you want a side-by-side example with
real backends such as Qdrant and LanceDB.
"""

import asyncio
from typing import Any, Dict, List, Optional

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs


class InMemoryVectorStore(vs.VectorStore):
    """Minimal VectorStore implementation you can copy into your own backend adapter."""

    def __init__(self) -> None:
        self.storage: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        print("Connected in-memory vector store")

    async def close(self) -> None:
        print("Closed in-memory vector store")

    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        metadata = metadata or [{} for _ in ids]

        for doc_id, embedding, document, meta in zip(ids, embeddings, documents, metadata):
            self.storage[doc_id] = {
                "embedding": embedding,
                "document": document,
                "metadata": meta,
            }

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        del query_embedding, filter_metadata

        results = []
        for doc_id, row in list(self.storage.items())[:top_k]:
            results.append(
                {
                    "id": doc_id,
                    "document": row["document"],
                    "score": 0.95,
                    "metadata": row["metadata"],
                }
            )
        return results

    async def delete(self, ids: List[str]) -> None:
        for doc_id in ids:
            self.storage.pop(doc_id, None)


async def main() -> None:
    print("=" * 60)
    print("LexiRedact - Minimal Custom Vector Store")
    print("=" * 60)
    print()

    store = InMemoryVectorStore()
    pipeline = vs.IngestionPipeline(vectorstore=store)
    await pipeline.initialize()

    documents = [
        vs.Document(
            id="user-1",
            text="User John Doe registered with email john@example.com",
            metadata={"type": "user_registration"},
        ),
        vs.Document(
            id="billing-1",
            text="The refund workflow requires manager approval and invoice review",
            metadata={"type": "billing_workflow"},
        ),
    ]

    batch_result = await pipeline.process_batch(documents)

    print("Stored sanitized documents:")
    for item in batch_result["results"]:
        print(f"   {item['id']}: {item['clean_text']}")
        print(f"      PII found: {item['pii_found']}")
    print()

    query = "How are invoice refunds reviewed?"
    results = await pipeline.retrieve(query_text=query, top_k=2)
    print(f"Sample query: {query}")
    for index, item in enumerate(results, start=1):
        print(f"   {index}. {item['id']} score={item['score']:.4f}")
        print(f"      {item['document']}")
    print()

    print("What to copy from this example:")
    print("   - The adapter only implements `connect`, `close`, `add_vectors`, `query`, and `delete`.")
    print("   - LexiRedact still handles PII detection, redaction, metrics, and embeddings.")
    print("   - Your real backend only needs to store sanitized text plus vectors.")

    await pipeline.shutdown()
    print()
    print("See `custom_vectordb_comparison.py` for Qdrant and LanceDB adapters.")


if __name__ == "__main__":
    asyncio.run(main())
