"""Quick start for LexiRedact ingestion.

Requires:
    pip install "lexiredact[pii]"
    python -m spacy download en_core_web_lg

This example uses a deterministic embedder and in-memory store so it does not
download an embedding model or require Chroma.
"""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401
from _embedding_reference import DeterministicEmbedder, InMemoryVectorStore

from lexiredact import LexiredactPipeline, load_config


config = load_config(
    {
        "pipeline_mode": "dual",
        "input_schema": {
            "id_field": "id",
            "text_field": "text",
            "metadata_fields": ["source"],
        },
        "pii": {
            "entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
            "language": "en",
            "nlp_engine": "spacy",
            "nlp_model": "en_core_web_lg",
            "score_threshold": 0.5,
        },
        "embedder": {"dimension": 4},
        "store": {"collection_name": "quickstart"},
    }
)

store = InMemoryVectorStore()
pipeline = LexiredactPipeline(
    config,
    embedder=DeterministicEmbedder(dimension=4),
    store=store,
)

results = pipeline.ingest(
    [
        {
            "id": "case-001",
            "text": "Jane Doe emailed jane.doe@example.com about the merger.",
            "source": "crm",
        },
        {
            "id": "case-002",
            "text": "Call John Smith at 212-555-0199 before filing.",
            "source": "ticket",
        },
    ]
)

for result in results:
    print(result.to_dict())

print(f"Stored records: {store.count()}")
print(store.records)
