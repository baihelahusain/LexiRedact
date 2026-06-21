"""
exceptions.py — Custom exception hierarchy for Lexiredact.

All public-facing errors inherit from LexiredactError.
Internal errors (e.g. cache) are caught internally and never raised to callers.
"""

from __future__ import annotations


class LexiredactError(Exception):
    """Base exception for all Lexiredact errors.

    Args:
        message: Human-readable description of the error.
        context: Optional dict with structured debug info (field names, values, etc.).
    """

    def __init__(self, message: str, context: dict | None = None) -> None:
        self.message = message
        self.context = context
        super().__init__(message)

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} [{ctx_str}]"
        return self.message


class LexiredactConfigError(LexiredactError):
    """Raised when configuration is invalid, missing required fields, or has unknown keys.

    Only raised at startup / config load time — never during pipeline execution.
    """


class LexiredactInputError(LexiredactError):
    """Raised when a chunk input dict is malformed, missing fields, or has empty text.

    Raised exclusively in ChunkAdapter. Never raised inside pipeline core.
    """


class LexiredactStorageError(LexiredactError):
    """Raised when a vector DB write operation fails.

    Bubbles up to the caller and is NOT caught internally.
    """


class LexiredactCacheError(LexiredactError):
    """Raised on Redis failures (connection errors, serialisation issues, etc.).

    NEVER propagated to callers. Caught silently inside the cache module,
    which logs a warning and falls through to the model inference path.
    """
