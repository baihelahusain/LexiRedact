"""
pipeline/embedder/registry.py — Embedder factory for lexiredact.

Single public function ``create_embedder(config)`` that reads
``EmbedderConfig.backend`` and returns the appropriate implementation.

Why lazy imports inside branches:
  Avoids importing ``torch`` / ``sentence_transformers`` / ``transformers``
  unless the corresponding backend is actually selected. This keeps import
  time low when using only one backend.

Supported backends:
  - ``"sentence_transformers"`` → ``SentenceTransformerEmbedder``
  - ``"huggingface"``           → ``HuggingFaceEmbedder``

All returned instances implement ``EmbedderBase`` and expose:
  ``embed_batch(texts)``  — document ingestion
  ``query_embed(texts)``  — retrieval queries
  ``get_dimension()``     — vector dimension (may trigger model load)
"""

from __future__ import annotations

from lexiredact.config.schema import EmbedderConfig
from lexiredact.pipeline.embedder.base import EmbedderBase


def create_embedder(config: EmbedderConfig) -> EmbedderBase:
    """Instantiate the correct embedder implementation based on config.backend.

    Args:
        config: Validated EmbedderConfig with backend field set.

    Returns:
        An EmbedderBase instance ready for use (model not yet loaded — lazy).

    Raises:
        LexiredactConfigError: If backend value is not recognised.
    """
    if config.backend == "sentence_transformers":
        from lexiredact.pipeline.embedder.sentence_transformers import (
            SentenceTransformerEmbedder,
        )
        return SentenceTransformerEmbedder(config)

    elif config.backend == "huggingface":
        from lexiredact.pipeline.embedder.huggingface import HuggingFaceEmbedder
        return HuggingFaceEmbedder(config)

    else:
        from lexiredact.exceptions import LexiredactConfigError
        raise LexiredactConfigError(
            f"Unknown embedder backend: '{config.backend}'",
            context={"supported": ["sentence_transformers", "huggingface"], "got": config.backend},
        )