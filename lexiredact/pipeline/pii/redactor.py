"""
pipeline/pii/redactor.py — Stateless PII text redaction via Presidio AnonymizerEngine.

Accepts the ORIGINAL text plus a pre-computed list of DetectedEntity spans and
returns sanitized text with each span replaced by a descriptive placeholder such
as ``<PERSON>`` or ``<EMAIL_ADDRESS>``.

This class deliberately does NOT call AnalyzerEngine — entity spans are always
provided by PIIDetector. Keeping detection and redaction separate allows the Phase 3
orchestrator to run redaction concurrently with embedding via asyncio.gather().

Thread safety: PIIRedactor holds no per-call state. A single instance can be used
concurrently from multiple coroutines or threads without synchronisation.
"""

from __future__ import annotations

from lexiredact.app_logging import get_logger
from lexiredact.models.result import DetectedEntity

logger = get_logger(__name__)


class PIIRedactor:
    """Replaces PII spans in text with ``<ENTITY_TYPE>`` placeholders.

    Wraps Presidio AnonymizerEngine with a fixed "replace" operator per entity type.
    The operator mapping is built dynamically from the entity list passed at call time,
    so no configuration is needed at construction.
    """

    def __init__(self) -> None:
        from presidio_anonymizer import AnonymizerEngine  # type: ignore[import-untyped]

        self._anonymizer = AnonymizerEngine()
        logger.info("PIIRedactor initialized.")

    def redact(self, text: str, entities: list[DetectedEntity]) -> str:
        """Replace each detected PII span with a ``<ENTITY_TYPE>`` placeholder.

        Args:
            text:     The ORIGINAL (un-sanitised) chunk text.
            entities: Entity spans from PIIDetector. Empty list → text returned unchanged.

        Returns:
            Sanitised text, or the original text unchanged if entities is empty.
        """
        if not entities:
            return text

        from presidio_anonymizer.entities import (  # type: ignore[import-untyped]
            OperatorConfig,
            RecognizerResult,
        )

        recognizer_results: list[RecognizerResult] = [
            RecognizerResult(
                entity_type=e.entity_type,
                start=e.start,
                end=e.end,
                score=e.score,
            )
            for e in entities
        ]
        operators: dict[str, OperatorConfig] = {
            e.entity_type: OperatorConfig("replace", {"new_value": f"<{e.entity_type}>"})
            for e in entities
        }
        result = self._anonymizer.anonymize(
            text=text,
            analyzer_results=recognizer_results,
            operators=operators,
        )
        logger.debug(
            "Redacted %d entity span(s). original_len=%d sanitized_len=%d",
            len(entities), len(text), len(result.text),
        )
        return result.text
