"""
adapters/chunk_adapter.py — Maps raw user input dicts to internal Chunk objects.

Field names are never hardcoded here; they are always read from InputSchemaConfig.
This is the only place in the codebase that performs per-chunk input validation.
"""

from __future__ import annotations

from typing import Any

from lexiredact.config.schema import InputSchemaConfig
from lexiredact.exceptions import LexiredactInputError
from lexiredact.app_logging import get_logger
from lexiredact.models.chunk import Chunk

logger = get_logger(__name__)


class ChunkAdapter:
    """Converts arbitrary user input dicts into validated Chunk objects.

    Args:
        config: Field-name mapping configuration from InputSchemaConfig.
    """

    def __init__(self, config: InputSchemaConfig) -> None:
        self._config = config

    def adapt(self, raw: dict[str, Any]) -> Chunk:
        """Convert a single raw input dict into a Chunk.

        Raises:
            LexiredactInputError: If id_field missing, text_field missing,
                or text is empty after stripping whitespace.
        """
        cfg = self._config

        if cfg.id_field not in raw:
            raise LexiredactInputError(
                f"Missing required id field '{cfg.id_field}' in input dict.",
                context={
                    "expected_id_field": cfg.id_field,
                    "available_keys": list(raw.keys()),
                },
            )

        chunk_id = str(raw[cfg.id_field])

        if cfg.text_field not in raw:
            raise LexiredactInputError(
                f"Missing required text field '{cfg.text_field}' in chunk '{chunk_id}'.",
                context={
                    "expected_text_field": cfg.text_field,
                    "available_keys": list(raw.keys()),
                    "chunk_id": chunk_id,
                },
            )

        text: str = raw[cfg.text_field]
        metadata: dict[str, Any] = {
            key: raw[key] for key in cfg.metadata_fields if key in raw
        }

        # Chunk.__post_init__ raises LexiredactInputError if text is empty.
        return Chunk(id=chunk_id, text=text, metadata=metadata)

    def adapt_batch(
        self, raws: list[dict[str, Any]]
    ) -> tuple[list[Chunk], list[dict[str, Any]]]:
        """Convert a list of raw dicts, collecting — not raising — per-item errors.

        Returns:
            (successful_chunks, failed_items)
            failed_items entries: {"index": int, "error": str, "raw": dict}
        """
        successful_chunks: list[Chunk] = []
        failed_items: list[dict[str, Any]] = []

        for index, raw in enumerate(raws):
            try:
                successful_chunks.append(self.adapt(raw))
            except LexiredactInputError as exc:
                logger.warning("Chunk at index %d failed adaptation: %s", index, exc)
                failed_items.append({"index": index, "error": str(exc), "raw": raw})

        if failed_items:
            logger.warning(
                "adapt_batch: %d/%d chunks failed. Proceeding with %d successful.",
                len(failed_items), len(raws), len(successful_chunks),
            )

        return successful_chunks, failed_items
