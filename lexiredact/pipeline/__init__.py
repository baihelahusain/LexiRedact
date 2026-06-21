"""
pipeline — Core processing modules for the Lexiredact dual pipeline.

Sub-packages:
  pii/      — Presidio-based PII detection (detector.py) and redaction (redactor.py).
  embedder/ — Abstract embedding interface (base.py) and default e5 model (default.py).

Orchestration (orchestrator.py) is added in Phase 3. It imports from both sub-packages
and uses asyncio.gather() to run redaction and embedding concurrently per chunk.
"""
