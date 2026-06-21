"""
pipeline/embedder/huggingface.py — HuggingFace AutoModel backend embedder.

Uses ``transformers.AutoModel`` + ``AutoTokenizer`` with mean-pooling over the
last hidden state. Suitable for any HuggingFace model not listed on the
sentence-transformers hub, or when you need direct control over the tokenization
and pooling strategy.

Dimension detection:
  Dimension is read from ``model.config.hidden_size`` after the model is loaded
  if ``EmbedderConfig.dimension`` is not set explicitly.

Prefixes:
  Applied from config just like ``SentenceTransformerEmbedder``. Leave
  ``document_prefix`` and ``query_prefix`` as empty strings for models that
  do not use asymmetric prefixes (e.g. standard BERT NER models).

Error handling:
  Raises ``LexiredactConfigError`` (not ``ImportError``) when the
  ``transformers`` package is not installed, so the failure message is
  consistent with the rest of the codebase.

Note:
  This class runs inference synchronously. The orchestrator wraps it in
  ``run_in_executor()`` so it does not block the asyncio event loop.
"""

from __future__ import annotations

from lexiredact.config.schema import EmbedderConfig
from lexiredact.app_logging import get_logger
from lexiredact.pipeline.embedder.base import EmbedderBase


class HuggingFaceEmbedder(EmbedderBase):
    """Embeds text using a raw HuggingFace AutoModel with mean-pooling.

    Suitable for encoder models (BERT, RoBERTa, DistilBERT, etc.) that are not
    packaged as sentence-transformers. Output dimension is inferred from
    ``model.config.hidden_size`` after the first load.

    Args:
        config: EmbedderConfig controlling model, batch size, device,
                normalization, prefixes, and optional dimension override.
    """

    def __init__(self, config: EmbedderConfig) -> None:
        self._config = config
        self._model = None       # AutoModel instance; loaded lazily.
        self._tokenizer = None   # AutoTokenizer instance; loaded lazily.
        self._dimension: int | None = config.dimension
        self._logger = get_logger("embedder.huggingface")

    # ------------------------------------------------------------------
    # EmbedderBase interface
    # ------------------------------------------------------------------

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts using mean-pooled last hidden state.

        Prepends ``EmbedderConfig.document_prefix`` if non-empty.

        Args:
            texts: Plain text strings. Must not be empty strings.

        Returns:
            One float vector per input text, in the same order.
        """
        if not texts:
            return []
        self._ensure_loaded()
        prefixed = self._apply_prefix(texts, self._config.document_prefix)
        return self._encode(prefixed)

    def query_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed query strings using mean-pooled last hidden state.

        Prepends ``EmbedderConfig.query_prefix`` if non-empty.

        Args:
            texts: Raw query strings (no prefix).

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

        Triggers a lazy model load if the dimension is not yet known.

        Returns:
            Integer vector dimension (e.g. 768 for BERT-base).
        """
        if self._dimension is not None:
            return self._dimension
        self._ensure_loaded()
        return self._dimension  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the AutoModel and AutoTokenizer on first use (lazy initialisation)."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModel, AutoTokenizer  # type: ignore[import-untyped]
        except ImportError as exc:
            from lexiredact.exceptions import LexiredactConfigError
            raise LexiredactConfigError(
                "huggingface backend requires the 'transformers' package: "
                "pip install transformers torch",
                context={"error": str(exc)},
            ) from exc

        self._logger.info(
            "Loading HuggingFaceEmbedder: model=%s device=%s",
            self._config.model_name,
            self._config.device,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(self._config.model_name)
        self._model = AutoModel.from_pretrained(self._config.model_name)
        self._model.eval()

        if self._dimension is None:
            self._dimension = self._model.config.hidden_size

        self._logger.info(
            "HuggingFaceEmbedder loaded: %s dim=%d",
            self._config.model_name,
            self._dimension,
        )

        # Move model to the requested device if specified and not cpu
        if self._config.device not in ("cpu", ""):
            try:
                self._model = self._model.to(self._config.device)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Could not move model to device '%s': %s. Falling back to cpu.",
                    self._config.device,
                    exc,
                )

    @staticmethod
    def _apply_prefix(texts: list[str], prefix: str) -> list[str]:
        """Prepend prefix to each text if prefix is non-empty."""
        if not prefix:
            return texts
        return [f"{prefix}{t}" for t in texts]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """Tokenize, run model, mean-pool, and return list[list[float]]."""
        import torch  # type: ignore[import-untyped]

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), self._config.batch_size):
            sub_batch = texts[i: i + self._config.batch_size]
            self._logger.debug(
                "Encoding sub-batch %d–%d of %d texts.",
                i,
                min(i + self._config.batch_size, len(texts)) - 1,
                len(texts),
            )
            encoded = self._tokenizer(  # type: ignore[operator]
                sub_batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            # Move inputs to device
            if self._config.device not in ("cpu", ""):
                try:
                    encoded = {k: v.to(self._config.device) for k, v in encoded.items()}
                except Exception:  # noqa: BLE001
                    pass

            with torch.no_grad():
                model_output = self._model(**encoded)  # type: ignore[operator]

            pooled = self._mean_pool(model_output, encoded["attention_mask"])
            all_vectors.extend(pooled)

        return all_vectors

    def _mean_pool(self, model_output, attention_mask) -> list[list[float]]:
        """Mean-pool last hidden state with attention mask, optionally normalise."""
        import torch  # type: ignore[import-untyped]

        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        )
        pooled = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )

        if self._config.normalize_embeddings:
            import torch.nn.functional as F  # type: ignore[import-untyped]
            pooled = F.normalize(pooled, p=2, dim=1)

        return pooled.detach().cpu().numpy().tolist()