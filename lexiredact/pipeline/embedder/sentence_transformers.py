"""
pipeline/embedder/sentence_transformers.py — SentenceTransformer backend embedder.

Uses the ``sentence-transformers`` library to encode text. Prefixes (e.g. the
``"passage: "`` / ``"query: "`` required by e5 models) are config-driven via
``EmbedderConfig.document_prefix`` and ``EmbedderConfig.query_prefix`` — they
are NOT hardcoded in this class, making this embedder safe for non-e5 models
(BGE, MiniLM, MPNet, etc.) that require no prefix.

Dimension detection:
  Loaded lazily on the first ``embed_batch`` or ``query_embed`` call. If
  ``EmbedderConfig.dimension`` is set, it is used immediately (allows
  ChromaStore construction without triggering a model download). Otherwise,
  the dimension is read from ``model.get_sentence_embedding_dimension()``
  after the first load and cached on the instance.

Phase 3 integration note:
  The orchestrator wraps ``embed_batch`` in ``run_in_executor()`` because
  sentence-transformers inference is synchronous and CPU/GPU-bound. This class
  does not need to be aware of the event loop.
"""

from __future__ import annotations

from lexiredact.config.schema import EmbedderConfig
from lexiredact.app_logging import get_logger
from lexiredact.pipeline.embedder.base import EmbedderBase


class SentenceTransformerEmbedder(EmbedderBase):
    """Embeds text using any sentence-transformers compatible model.

    Prefixes are applied from config:
      - ``EmbedderConfig.document_prefix`` → prepended during ingestion
      - ``EmbedderConfig.query_prefix``    → prepended during retrieval

    Leave both prefix fields as empty strings for models that do not require
    any prefix (e.g. ``all-MiniLM-L6-v2``, ``bge-small-en``).

    Args:
        config: EmbedderConfig controlling model, batch size, device,
                normalization, prefixes, and optional dimension override.
    """

    def __init__(self, config: EmbedderConfig) -> None:
        self._config = config
        self._model = None  # SentenceTransformer instance; loaded lazily on first call.
        # Pre-populate if config provides an explicit dimension override.
        self._dimension: int | None = config.dimension
        self._logger = get_logger("embedder.sentence_transformers")

    # ------------------------------------------------------------------
    # EmbedderBase interface
    # ------------------------------------------------------------------

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts.

        Prepends ``EmbedderConfig.document_prefix`` to each text (if non-empty),
        then encodes in sub-batches of ``EmbedderConfig.batch_size``. Numpy
        output is converted to ``list[list[float]]`` before returning.

        Args:
            texts: Plain text strings (original or sanitised, depending on
                   ``pipeline_mode``). Must not be empty strings — callers are
                   responsible for filtering.

        Returns:
            One float vector per input text, in the same order.
        """
        if not texts:
            return []

        self._ensure_loaded()
        prefixed = self._apply_prefix(texts, self._config.document_prefix)
        return self._encode(prefixed)

    def query_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed query strings with the query prefix required by asymmetric models.

        Prepends ``EmbedderConfig.query_prefix`` to each text (if non-empty).
        Using the wrong prefix at query time causes silent but significant
        retrieval quality degradation for e5-style models.

        Args:
            texts: Raw query strings (without any prefix).

        Returns:
            One float vector per input text, in the same order.
        """
        if not texts:
            return []

        self._ensure_loaded()
        prefixed = self._apply_prefix(texts, self._config.query_prefix)
        return self._encode(prefixed)

    def get_dimension(self) -> int:
        """Return the vector dimension of this embedder.

        If ``EmbedderConfig.dimension`` was set, returns it without loading
        the model. Otherwise triggers a lazy model load to detect the
        dimension from ``model.get_sentence_embedding_dimension()``.

        Returns:
            Integer vector dimension (e.g. 384 for e5-small-v2).
        """
        if self._dimension is not None:
            return self._dimension
        self._ensure_loaded()
        return self._dimension  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the SentenceTransformer model on first use (lazy initialisation).

        Subsequent calls are no-ops. After loading, caches the dimension
        on the instance if it was not pre-configured.
        """
        if self._model is not None:
            return

        # Import inside method so the module is importable without sentence-transformers.
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        self._logger.info(
            "Loading SentenceTransformerEmbedder: model=%s device=%s",
            self._config.model_name,
            self._config.device,
        )
        self._model = SentenceTransformer(self._config.model_name, device=self._config.device)

        if self._dimension is None:
            self._dimension = self._model.get_sentence_embedding_dimension()

        self._logger.info(
            "SentenceTransformerEmbedder loaded: %s dim=%d",
            self._config.model_name,
            self._dimension,
        )

    @staticmethod
    def _apply_prefix(texts: list[str], prefix: str) -> list[str]:
        """Prepend prefix to each text if prefix is non-empty."""
        if not prefix:
            return texts
        return [f"{prefix}{t}" for t in texts]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts in sub-batches, returning list[list[float]]."""
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), self._config.batch_size):
            sub_batch = texts[i: i + self._config.batch_size]
            self._logger.debug(
                "Encoding sub-batch %d–%d of %d texts.",
                i,
                min(i + self._config.batch_size, len(texts)) - 1,
                len(texts),
            )
            vecs = self._model.encode(  # type: ignore[union-attr]
                sub_batch,
                normalize_embeddings=self._config.normalize_embeddings,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_vectors.extend(vecs.tolist())

        return all_vectors