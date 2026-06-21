"""
pipeline/orchestrator.py — Core dual pipeline orchestrator.

Routes each batch through one of three execution paths based on pipeline_mode:

  "dual"        → detect → asyncio.gather(redact, embed_original) → store sanitized
  "preredacted" → detect → redact → embed_sanitized → store sanitized  (sequential)
  "raw"         → embed_original → store_original                      (no PII step)

Original text NEVER reaches the vector store in dual or preredacted mode.

Stage timing:
  Each ProcessingResult includes stage_latencies with per-stage wall-clock ms.
  When a batch of N chunks is processed, the total elapsed time is divided by N
  to produce a per-chunk average latency_ms. Stage timings follow the same
  division so that each result reflects the per-chunk cost of that stage.
"""

from __future__ import annotations

import asyncio
import time

from lexiredact.cache.redis_cache import EmbeddingCache
from lexiredact.config.schema import LexiredactConfig
from lexiredact.exceptions import LexiredactConfigError, LexiredactStorageError
from lexiredact.app_logging import get_logger
from lexiredact.models.chunk import Chunk
from lexiredact.models.result import DetectedEntity, ProcessingResult
from lexiredact.pipeline.embedder.base import EmbedderBase
from lexiredact.pipeline.pii.detector import PIIDetector
from lexiredact.pipeline.pii.redactor import PIIRedactor
from lexiredact.pipeline.store.base import VectorStoreBase

logger = get_logger(__name__)


class Orchestrator:
    """Coordinates PII detection, redaction, embedding, caching, and storage.

    Args:
        config:   Full pipeline configuration.
        embedder: Embedding model (lazy-loaded on first call).
        store:    Vector database implementation.
        cache:    Embedding cache (transparent no-op when disabled).
    """

    def __init__(
        self,
        config: LexiredactConfig,
        embedder: EmbedderBase,
        store: VectorStoreBase,
        cache: EmbeddingCache,
    ) -> None:
        self._config = config
        self._detector = PIIDetector(config.pii)
        self._redactor = PIIRedactor()
        self._embedder = embedder
        self._store = store
        self._cache = cache
        self._logger = get_logger("pipeline.orchestrator")

    async def process_batch(self, chunks: list[Chunk]) -> list[ProcessingResult]:
        """Route chunks through the configured pipeline mode.

        Returns results in the same order as input. LexiredactStorageError bubbles up.
        """
        t0 = time.perf_counter()
        mode = self._config.pipeline_mode

        match mode:
            case "dual":
                results = await self._run_dual(chunks)
            case "preredacted":
                results = await self._run_preredacted(chunks)
            case "raw":
                results = await self._run_raw(chunks)
            case _:
                raise LexiredactConfigError(
                    f"Unknown pipeline_mode: {mode!r}",
                    context={"pipeline_mode": mode},
                )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._logger.info(
            "Processed %d chunks in %.1fms (mode=%s)", len(chunks), elapsed_ms, mode
        )
        return results

    async def _run_dual(self, chunks: list[Chunk]) -> list[ProcessingResult]:
        """DUAL MODE: parallel redaction + embedding from original text."""
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        n = len(chunks)

        # Step 1: PII detection (sequential, must finish before parallel phase)
        t_pii_start = time.perf_counter()
        entity_lists: list[list[DetectedEntity]] = self._detector.detect_batch(chunks)
        pii_ms = (time.perf_counter() - t_pii_start) * 1000

        # Step 2: Parallel — redact and embed run concurrently via asyncio.gather()
        async def redact_all() -> list[str]:
            return await loop.run_in_executor(
                None,
                lambda: [
                    self._redactor.redact(chunk.text, entities)
                    for chunk, entities in zip(chunks, entity_lists)
                ],
            )

        async def embed_all() -> tuple[list[list[float]], list[bool]]:
            texts = [chunk.text for chunk in chunks]
            cached_vectors: list[list[float] | None] = [
                self._cache.get(t) for t in texts
            ]
            miss_indices = [i for i, v in enumerate(cached_vectors) if v is None]
            miss_texts = [texts[i] for i in miss_indices]

            if miss_texts:
                new_vectors: list[list[float]] = await loop.run_in_executor(
                    None, lambda: self._embedder.embed_batch(miss_texts)
                )
                for idx, vec in zip(miss_indices, new_vectors):
                    cached_vectors[idx] = vec
                    self._cache.set(texts[idx], vec)

            cache_hits = [i not in miss_indices for i in range(len(chunks))]
            return cached_vectors, cache_hits  # type: ignore[return-value]

        # asyncio.gather: both coroutines run concurrently — never sequentially.
        t_parallel_start = time.perf_counter()
        sanitized_texts, (vectors, cache_hits) = await asyncio.gather(
            redact_all(), embed_all()
        )
        parallel_ms = (time.perf_counter() - t_parallel_start) * 1000

        # Step 3: Storage — sanitized text only, original never touches the DB.
        t_store_start = time.perf_counter()
        embedding_stored = True
        try:
            self._store.upsert_batch(
                ids=[c.id for c in chunks],
                vectors=vectors,
                metadatas=[
                    {"text": sanitized_texts[i], **chunks[i].metadata}
                    for i in range(len(chunks))
                ],
            )
        except LexiredactStorageError:
            embedding_stored = False
            raise  # Data loss must never be silent.
        store_ms = (time.perf_counter() - t_store_start) * 1000

        total_ms = (time.perf_counter() - t0) * 1000
        latency_ms = self._per_chunk_latency(total_ms / 1000, n)

        # Per-chunk stage latencies — divide batch totals by n for per-chunk average
        per_chunk_pii_ms = pii_ms / max(n, 1)
        per_chunk_parallel_ms = parallel_ms / max(n, 1)
        per_chunk_store_ms = store_ms / max(n, 1)

        return [
            ProcessingResult(
                chunk_id=chunks[i].id,
                sanitized_text=sanitized_texts[i],
                entities_detected=entity_lists[i],
                embedding_stored=embedding_stored,
                latency_ms=latency_ms,
                cache_hit=cache_hits[i],
                pipeline_mode="dual",
                stage_latencies={
                    "pii_ms": round(per_chunk_pii_ms, 2),
                    "embed_redact_ms": round(per_chunk_parallel_ms, 2),
                    "store_ms": round(per_chunk_store_ms, 2),
                },
            )
            for i in range(n)
        ]

    async def _run_preredacted(self, chunks: list[Chunk]) -> list[ProcessingResult]:
        """PREREDACTED MODE: sequential detect → redact → embed(sanitized) → store."""
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        n = len(chunks)

        t_pii_start = time.perf_counter()
        entity_lists: list[list[DetectedEntity]] = self._detector.detect_batch(chunks)
        pii_ms = (time.perf_counter() - t_pii_start) * 1000

        t_redact_start = time.perf_counter()
        sanitized_texts: list[str] = [
            self._redactor.redact(chunk.text, entities)
            for chunk, entities in zip(chunks, entity_lists)
        ]
        redact_ms = (time.perf_counter() - t_redact_start) * 1000

        # Embed sanitized text — NOT original. This is the key difference from dual.
        t_embed_start = time.perf_counter()
        vectors: list[list[float]] = await loop.run_in_executor(
            None, lambda: self._embedder.embed_batch(sanitized_texts)
        )
        embed_ms = (time.perf_counter() - t_embed_start) * 1000

        t_store_start = time.perf_counter()
        embedding_stored = True
        try:
            self._store.upsert_batch(
                ids=[c.id for c in chunks],
                vectors=vectors,
                metadatas=[
                    {"text": sanitized_texts[i], **chunks[i].metadata}
                    for i in range(len(chunks))
                ],
            )
        except LexiredactStorageError:
            embedding_stored = False
            raise
        store_ms = (time.perf_counter() - t_store_start) * 1000

        total_ms = (time.perf_counter() - t0) * 1000
        latency_ms = self._per_chunk_latency(total_ms / 1000, n)

        per_chunk_pii_ms = pii_ms / max(n, 1)
        per_chunk_redact_ms = redact_ms / max(n, 1)
        per_chunk_embed_ms = embed_ms / max(n, 1)
        per_chunk_store_ms = store_ms / max(n, 1)

        return [
            ProcessingResult(
                chunk_id=chunks[i].id,
                sanitized_text=sanitized_texts[i],
                entities_detected=entity_lists[i],
                embedding_stored=embedding_stored,
                latency_ms=latency_ms,
                cache_hit=False,  # Sanitized text has different hash; cache not useful.
                pipeline_mode="preredacted",
                stage_latencies={
                    "pii_ms": round(per_chunk_pii_ms, 2),
                    "redact_ms": round(per_chunk_redact_ms, 2),
                    "embed_ms": round(per_chunk_embed_ms, 2),
                    "store_ms": round(per_chunk_store_ms, 2),
                },
            )
            for i in range(n)
        ]

    async def _run_raw(self, chunks: list[Chunk]) -> list[ProcessingResult]:
        """RAW MODE: no PII step — embed and store original text (eval baseline only)."""
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        n = len(chunks)

        texts = [chunk.text for chunk in chunks]
        cached_vectors: list[list[float] | None] = [self._cache.get(t) for t in texts]
        miss_indices = [i for i, v in enumerate(cached_vectors) if v is None]
        miss_texts = [texts[i] for i in miss_indices]

        t_embed_start = time.perf_counter()
        if miss_texts:
            new_vectors: list[list[float]] = await loop.run_in_executor(
                None, lambda: self._embedder.embed_batch(miss_texts)
            )
            for idx, vec in zip(miss_indices, new_vectors):
                cached_vectors[idx] = vec
                self._cache.set(texts[idx], vec)
        embed_ms = (time.perf_counter() - t_embed_start) * 1000

        vectors: list[list[float]] = cached_vectors  # type: ignore[assignment]
        cache_hits = [i not in miss_indices for i in range(len(chunks))]

        # Store original text in metadata — intentional in raw mode only.
        t_store_start = time.perf_counter()
        embedding_stored = True
        try:
            self._store.upsert_batch(
                ids=[c.id for c in chunks],
                vectors=vectors,
                metadatas=[{"text": chunk.text, **chunk.metadata} for chunk in chunks],
            )
        except LexiredactStorageError:
            embedding_stored = False
            raise
        store_ms = (time.perf_counter() - t_store_start) * 1000

        total_ms = (time.perf_counter() - t0) * 1000
        latency_ms = self._per_chunk_latency(total_ms / 1000, n)

        per_chunk_embed_ms = embed_ms / max(n, 1)
        per_chunk_store_ms = store_ms / max(n, 1)

        return [
            ProcessingResult(
                chunk_id=chunks[i].id,
                sanitized_text="",     # No redaction happened.
                entities_detected=[],  # No detection happened.
                embedding_stored=embedding_stored,
                latency_ms=latency_ms,
                cache_hit=cache_hits[i],
                pipeline_mode="raw",
                stage_latencies={
                    "embed_ms": round(per_chunk_embed_ms, 2),
                    "store_ms": round(per_chunk_store_ms, 2),
                },
            )
            for i in range(n)
        ]

    def _per_chunk_latency(self, total_seconds: float, n: int) -> float:
        """Average per-chunk latency in milliseconds."""
        return (total_seconds * 1000) / max(n, 1)