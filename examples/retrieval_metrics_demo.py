"""Tiny retrieval metric demo using the example in-memory store."""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401
from _embedding_reference import DeterministicEmbedder, InMemoryVectorStore


embedder = DeterministicEmbedder(dimension=6)
store = InMemoryVectorStore()

documents = {
    "doc-1": "Contract renewal and invoice approval.",
    "doc-2": "Password reset and account recovery instructions.",
    "doc-3": "Employment agreement with confidentiality clause.",
}

store.upsert_batch(
    ids=list(documents),
    vectors=embedder.embed_batch(list(documents.values())),
    metadatas=[{"text": text} for text in documents.values()],
)

queries = [
    ("contract approval", "doc-1"),
    ("confidential agreement", "doc-3"),
]

hits = 0
for query, expected_id in queries:
    query_vector = embedder.query_embed([query])[0]
    top = store.query(query_vector, top_k=1)[0]
    hits += int(top["id"] == expected_id)
    print({"query": query, "expected": expected_id, "top": top["id"]})

print({"recall_at_1": hits / len(queries)})
