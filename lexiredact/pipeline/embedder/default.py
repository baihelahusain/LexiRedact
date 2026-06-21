"""
pipeline/embedder/default.py — Backward-compatibility shim.

``DefaultEmbedder`` is now an alias for ``SentenceTransformerEmbedder``.
All existing code that imports ``DefaultEmbedder`` continues to work without
any changes. New code should import ``SentenceTransformerEmbedder`` directly
or use ``create_embedder(config)`` from the registry.
"""
from lexiredact.pipeline.embedder.sentence_transformers import (
    SentenceTransformerEmbedder as DefaultEmbedder,
)

__all__ = ["DefaultEmbedder"]