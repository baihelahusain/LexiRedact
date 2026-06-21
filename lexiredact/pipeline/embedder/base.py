"""
pipeline/embedder/base.py — Abstract base class for all LexiRedact embedding models.

No ML library imports appear here — this file has zero heavyweight dependencies so it
can be imported in any environment, including those without torch or sentence-transformers.

Both ``embed_batch`` and ``query_embed`` are abstract — all implementations must
provide both. The distinction between the two is purely semantic: ``embed_batch``
is called with document texts during ingestion, ``query_embed`` is called with
query strings at retrieval time. Implementations apply document_prefix and
query_prefix internally (from EmbedderConfig), not by the caller.

Implementing a custom embedder::

    from lexiredact.pipeline.embedder import EmbedderBase

    class MyEmbedder(EmbedderBase):
        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            ...  # apply document_prefix, call your model; return plain Python floats
        def query_embed(self, texts: list[str]) -> list[list[float]]:
            ...  # apply query_prefix, call your model; return plain Python floats
        def get_dimension(self) -> int:
            return 768

    pipeline = LexiredactPipeline(config, embedder=MyEmbedder())
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbedderBase(ABC):
    """Abstract interface for all embedding models used by lexiredact.

    Contract:
    - ``embed_batch`` receives plain text strings for document ingestion.
      Implementations prepend ``EmbedderConfig.document_prefix`` internally.
    - ``query_embed`` receives plain text strings for retrieval queries.
      Implementations prepend ``EmbedderConfig.query_prefix`` internally.
    - Output vectors must be ``list[list[float]]`` — never numpy arrays.
    - Return list must be same length as input list, in the same order.
    - ``get_dimension`` must return the correct length before any call.
      Implementations may trigger a model load internally if dimension is
      not yet known (i.e. no ``EmbedderConfig.dimension`` override was set).
    """

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts and return one vector per text.

        Implementations apply ``EmbedderConfig.document_prefix`` internally.

        Args:
            texts: Plain text strings to embed. Length may be 0 (return ``[]``).

        Returns:
            A list of float vectors in the same order as ``texts``.
            Each inner list has length equal to :meth:`get_dimension`.
            Numpy arrays must be converted to ``list[float]`` before returning.
        """
        ...

    @abstractmethod
    def query_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed query strings for retrieval. Implementations apply query_prefix internally.

        Semantically equivalent to ``embed_batch`` but uses
        ``EmbedderConfig.query_prefix`` instead of ``document_prefix``.
        Using the correct prefix at query time is critical for asymmetric
        embedding models like e5 — incorrect prefixes cause silent but
        significant retrieval quality degradation.

        Args:
            texts: Raw query strings (no prefix). Length may be 0 (return ``[]``).

        Returns:
            list[list[float]] in same order as texts, each of length
            :meth:`get_dimension`.
        """
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimensionality of the vectors produced by this embedder.

        Implementations must return a valid int even before the first
        ``embed_batch`` call. If the dimension is not known without loading
        the model (i.e. ``EmbedderConfig.dimension`` is ``None``), the
        implementation must call ``_ensure_loaded()`` internally.

        Returns:
            Integer vector length (e.g. 384 for e5-small-v2, 768 for BERT-base).
        """
        ...