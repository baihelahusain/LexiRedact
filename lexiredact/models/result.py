"""
models/result.py — Public-facing data contracts returned by the Lexiredact pipeline.

Both DetectedEntity and ProcessingResult are exported at the package root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectedEntity:
    """A single PII span detected by Presidio in the original text.

    Attributes:
        text:        The literal PII substring as it appeared in the original text.
        entity_type: Presidio entity label, e.g. "PERSON", "EMAIL_ADDRESS".
        start:       Start character offset (inclusive) within the original text.
        end:         End character offset (exclusive) within the original text.
        score:       Presidio confidence score in the range [0.0, 1.0].
    """

    text: str
    entity_type: str
    start: int
    end: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "score": self.score,
        }


@dataclass
class ProcessingResult:
    """Full processing outcome for a single chunk.

    Attributes:
        chunk_id:          The identifier of the processed chunk.
        sanitized_text:    PII-redacted text stored in the vector DB.
                           Empty string when pipeline_mode="raw".
        entities_detected: All PII spans found in the original text.
        embedding_stored:  True if the embedding was successfully persisted.
        latency_ms:        Wall-clock duration for the entire chunk, in milliseconds.
        cache_hit:         True if the embedding was retrieved from Redis cache.
        pipeline_mode:     One of "raw", "preredacted", or "dual".
        error:             Human-readable description of any partial failure. None on success.
        stage_latencies:   Optional breakdown of time spent per pipeline stage, in ms.
                           Keys vary by mode:
                             dual        — {"pii_ms", "embed_redact_ms", "store_ms"}
                             preredacted — {"pii_ms", "redact_ms", "embed_ms", "store_ms"}
                             raw         — {"embed_ms", "store_ms"}
                           None when not measured (e.g. batch-level timing).
    """

    chunk_id: str
    sanitized_text: str
    entities_detected: list[DetectedEntity]
    embedding_stored: bool
    latency_ms: float
    cache_hit: bool
    pipeline_mode: str
    error: str | None = None
    stage_latencies: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary. latency_ms rounded to 2 decimal places."""
        return {
            "chunk_id": self.chunk_id,
            "sanitized_text": self.sanitized_text,
            "entities_detected": [e.to_dict() for e in self.entities_detected],
            "embedding_stored": self.embedding_stored,
            "latency_ms": round(self.latency_ms, 2),
            "cache_hit": self.cache_hit,
            "pipeline_mode": self.pipeline_mode,
            "error": self.error,
            "stage_latencies": (
                {k: round(v, 2) for k, v in self.stage_latencies.items()}
                if self.stage_latencies else None
            ),
        }