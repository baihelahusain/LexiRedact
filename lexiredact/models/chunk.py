"""
models/chunk.py — Internal data transfer object representing a single text chunk.

Chunk is the canonical unit flowing through every stage of the pipeline.
It is NOT part of the public API and must not be exposed to callers directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lexiredact.exceptions import LexiredactInputError


@dataclass
class Chunk:
    """Internal representation of a single pre-chunked text unit.

    Attributes:
        id:       Unique identifier for this chunk (sourced from id_field).
        text:     Raw, unmodified original text. Never mutated after construction.
        metadata: Passthrough key-value pairs from InputSchemaConfig.metadata_fields.
    """

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate that text is not empty after stripping whitespace.

        Raises:
            LexiredactInputError: If the stripped text is an empty string.
        """
        if not self.text.strip():
            raise LexiredactInputError(
                f"chunk '{self.id}' has empty text field",
                context={"chunk_id": self.id},
            )
