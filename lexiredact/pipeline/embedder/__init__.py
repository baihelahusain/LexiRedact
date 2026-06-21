"""
pipeline/embedder — Abstract and concrete embedding implementations.

  EmbedderBase                — Abstract interface. Extend to plug in any model.
  SentenceTransformerEmbedder — Primary backend (sentence-transformers library).
                                Handles pooling, normalization, and prefix injection.
                                Covers e5, BGE, MiniLM, MPNet, and most Hub models.
  HuggingFaceEmbedder         — Secondary backend (raw transformers AutoModel).
                                Mean-pools last hidden state. Covers models not on
                                sentence-transformers hub.
  create_embedder             — Factory: instantiates the correct backend from EmbedderConfig.

Selecting a backend:
  Set EmbedderConfig.backend = "sentence_transformers" | "huggingface"
  Both implement embed_batch() and query_embed() on EmbedderBase.

Prefix configuration:
  Set EmbedderConfig.document_prefix / query_prefix in config.
  Default: "passage: " / "query: " for e5 compatibility.
  Set both to "" for non-e5 models (BGE, MiniLM, standard BERT, etc.).

Backward compatibility:
  ``DefaultEmbedder`` remains importable from ``pipeline/embedder/default.py``
  as an alias for ``SentenceTransformerEmbedder``.
"""

from lexiredact.pipeline.embedder.base import EmbedderBase
from lexiredact.pipeline.embedder.sentence_transformers import SentenceTransformerEmbedder
from lexiredact.pipeline.embedder.huggingface import HuggingFaceEmbedder
from lexiredact.pipeline.embedder.registry import create_embedder

__all__ = [
    "EmbedderBase",
    "SentenceTransformerEmbedder",
    "HuggingFaceEmbedder",
    "create_embedder",
]