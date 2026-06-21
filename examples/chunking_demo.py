"""Prepare pre-chunked records for LexiRedact."""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401

from lexiredact import load_config
from lexiredact.adapters.chunk_adapter import ChunkAdapter


config = load_config(
    {
        "input_schema": {
            "id_field": "chunk_id",
            "text_field": "body",
            "metadata_fields": ["source", "page"],
        }
    }
)

raw_chunks = [
    {
        "chunk_id": "contract-42:p1",
        "body": "Jane Doe signed the contract.",
        "source": "contract-42.pdf",
        "page": 1,
    },
    {
        "chunk_id": "contract-42:p2",
        "body": "   ",
        "source": "contract-42.pdf",
        "page": 2,
    },
]

adapter = ChunkAdapter(config.input_schema)
chunks, failed = adapter.adapt_batch(raw_chunks)

print("valid chunks:")
for chunk in chunks:
    print(chunk)

print("failed chunks:")
for item in failed:
    print(item["index"], item["error"])
