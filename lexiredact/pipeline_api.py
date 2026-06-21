"""
pipeline_api.py — Public entry point for the LexiRedact library.

This is the only module users need to interact with directly.

Usage::

    from lexiredact import LexiredactPipeline, load_config

    config = load_config("config.yaml")
    pipeline = LexiredactPipeline(config)
    results = pipeline.ingest([{"id": "c1", "text": "John called..."}])
"""

from __future__ import annotations

import asyncio
from typing import Any

from lexiredact.adapters.chunk_adapter import ChunkAdapter
from lexiredact.cache.redis_cache import EmbeddingCache
from lexiredact.config.schema import LexiredactConfig
from lexiredact.app_logging import get_logger
from lexiredact.models.result import ProcessingResult
from lexiredact.pipeline.embedder.base import EmbedderBase
from lexiredact.pipeline.embedder.registry import create_embedder
from lexiredact.pipeline.orchestrator import Orchestrator
from lexiredact.pipeline.store.base import VectorStoreBase
from lexiredact.pipeline.store.chroma import ChromaStore


class LexiredactPipeline:
    """The single public interface for LexiRedact ingestion.

    Args:
        config:   Full pipeline configuration from load_config().
        embedder: Optional custom embedder. Defaults to the backend specified
                  in ``config.embedder.backend`` via ``create_embedder()``.
        store:    Optional custom vector store. Defaults to ChromaStore (local).
    """

    def __init__(
        self,
        config: LexiredactConfig,
        embedder: EmbedderBase | None = None,
        store: VectorStoreBase | None = None,
    ) -> None:
        self._config = config
        self._adapter = ChunkAdapter(config.input_schema)
        self._logger = get_logger("pipeline_api")

        _embedder: EmbedderBase = embedder or create_embedder(config.embedder)
        _store: VectorStoreBase = store or ChromaStore(
            config.store, _embedder.get_dimension()
        )
        _cache = EmbeddingCache(config.cache)
        self._orchestrator = Orchestrator(config, _embedder, _store, _cache)

        self._logger.info(
            "LexiredactPipeline ready. mode=%s embedder=%s backend=%s",
            config.pipeline_mode,
            type(_embedder).__name__,
            config.embedder.backend,
        )

    def ingest(self, raw_chunks: list[dict[str, Any]]) -> list[ProcessingResult]:
        """Ingest raw chunk dicts through the configured pipeline.

        Partial failure: invalid chunks (missing fields, empty text) are skipped
        with a WARNING. LexiredactStorageError propagates to the caller.

        Args:
            raw_chunks: Pre-chunked input dicts. Field names controlled by
                        InputSchemaConfig (default: "id" and "text").

        Returns:
            ProcessingResult for each valid chunk, in the same order as input.
        """
        chunks, failed = self._adapter.adapt_batch(raw_chunks)
        for f in failed:
            self._logger.warning(
                "Skipping chunk at index %d: %s", f["index"], f["error"]
            )
        if not chunks:
            self._logger.warning("No valid chunks to process after adaptation.")
            return []
        self._logger.debug(
            "Ingesting %d valid chunk(s). %d skipped.", len(chunks), len(failed)
        )
        return asyncio.run(self._orchestrator.process_batch(chunks))