"""
pipeline/pii — Presidio-backed PII detection and redaction.

  PIIDetector — batch detection of entity spans from original Chunk text.
  PIIRedactor — stateless replacement of entity spans with <ENTITY_TYPE> placeholders.

These two classes are kept separate because in the dual pipeline they run on different
inputs: the detector runs first (sequential), the redactor runs concurrently with the
embedder (parallel) using the spans the detector already produced.
"""

from lexiredact.pipeline.pii.detector import PIIDetector
from lexiredact.pipeline.pii.redactor import PIIRedactor

__all__ = ["PIIDetector", "PIIRedactor"]
