"""
pipeline/pii/detector.py — Presidio-based batch PII detection.

Accepts batches of Chunk objects and returns the detected PII entity spans per chunk.
Detection is PURE — no text is modified here. The redactor (redactor.py) handles
replacement separately once the orchestrator decides which pipeline branch to follow.

NLP engine construction is delegated entirely to ``engine_factory.build_nlp_engine()``
which encapsulates spacy / transformers / stanza configuration logic. This module
only calls ``AnalyzerEngine`` with the already-constructed engine.

Design notes for Phase 3 orchestrator:
  - detect_batch() is synchronous and always runs BEFORE the parallel phase.
  - Its output (list[list[DetectedEntity]]) is passed as-is to the redactor coroutine.
  - The embedder coroutine receives the ORIGINAL chunk text, not the redacted output.
"""

from __future__ import annotations

from lexiredact.config.schema import PIIConfig
from lexiredact.app_logging import get_logger
from lexiredact.models.chunk import Chunk
from lexiredact.models.result import DetectedEntity

logger = get_logger(__name__)


class PIIDetector:
    """Wraps Presidio AnalyzerEngine to detect PII entity spans in batches of Chunks.

    Detection is read-only — text is never modified. Each call to ``detect_batch``
    returns one ``list[DetectedEntity]`` per input chunk, in the same order.

    The NLP engine (spacy / transformers / stanza) is selected by ``PIIConfig.nlp_engine``
    and the specific model by ``PIIConfig.nlp_model``. Engine construction is
    delegated to ``pipeline.pii.engine_factory.build_nlp_engine()``.

    Args:
        config: PII configuration controlling which entities to detect, the NLP
                engine and model to use, score filtering, and batch size.
    """

    def __init__(self, config: PIIConfig) -> None:
        self._config = config
        self._analyzer = None  # Loaded lazily on first detect_batch call.
        logger.info(
            "PIIDetector initialized: nlp_engine=%s nlp_model=%s",
            config.nlp_engine,
            config.nlp_model,
        )

    def detect_batch(self, chunks: list[Chunk]) -> list[list[DetectedEntity]]:
        """Detect PII entity spans across a batch of chunks.

        Processes chunks in sub-batches of ``PIIConfig.batch_size``. If detection
        fails for an individual chunk, a WARNING is logged and an empty list is
        returned for that chunk — processing continues for the remainder.

        Args:
            chunks: Ordered list of Chunk objects whose ``.text`` fields will be analysed.

        Returns:
            A list of the same length as ``chunks``. Each element is a
            ``list[DetectedEntity]`` (possibly empty) for the corresponding chunk.
            Return order matches input order exactly.
        """
        self._ensure_loaded()

        results: list[list[DetectedEntity]] = []
        batch_size = self._config.batch_size

        for batch_start in range(0, len(chunks), batch_size):
            sub_batch = chunks[batch_start: batch_start + batch_size]
            for chunk in sub_batch:
                results.append(self._detect_single(chunk))

        return results

    def _ensure_loaded(self) -> None:
        """Lazily initialise the Presidio AnalyzerEngine on first use.

        Delegates NLP engine construction to ``build_nlp_engine()`` so this
        method stays engine-agnostic.
        """
        if self._analyzer is not None:
            return

        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-untyped]
        from lexiredact.pipeline.pii.engine_factory import build_nlp_engine

        cfg = self._config
        logger.info(
            "Loading Presidio AnalyzerEngine: nlp_engine=%s nlp_model=%s lang=%s",
            cfg.nlp_engine,
            cfg.nlp_model,
            cfg.language,
        )
        nlp_engine = build_nlp_engine(cfg)
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        logger.info("Presidio AnalyzerEngine ready.")

    def _detect_single(self, chunk: Chunk) -> list[DetectedEntity]:
        """Run Presidio analysis on a single chunk and return filtered entities.

        Any exception from Presidio is caught; a WARNING is logged and an empty list
        is returned so that a single bad chunk never aborts the entire batch.
        """
        try:
            raw_results = self._analyzer.analyze(
                text=chunk.text,
                entities=self._config.entities,
                language=self._config.language,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("PII detection failed for chunk '%s': %s", chunk.id, exc)
            return []

        entities: list[DetectedEntity] = []
        for result in raw_results:
            if result.score < self._config.score_threshold:
                continue
            if result.entity_type not in self._config.entities:
                continue
            entities.append(
                DetectedEntity(
                    text=chunk.text[result.start: result.end],
                    entity_type=result.entity_type,
                    start=result.start,
                    end=result.end,
                    score=float(result.score),
                )
            )
        return entities