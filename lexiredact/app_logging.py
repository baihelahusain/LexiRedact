"""
logging.py — Centralised logging configuration for lexiredact.

Registers a NullHandler at import time so that library consumers who have
not configured logging do not receive "No handlers could be found" warnings.

Usage inside library modules:
    from lexiredact.logging import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging

# Register NullHandler at module-import time so LexiRedact is a well-behaved library.
logging.getLogger("lexiredact").addHandler(logging.NullHandler())

_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root ``LexiRedact`` logger with a StreamHandler.

    Adds a single StreamHandler pointing to stderr with the standard format.
    Safe to call multiple times — will not add duplicate handlers.

    Args:
        level: Logging level string, e.g. "DEBUG", "INFO", "WARNING".
    """
    root_logger = logging.getLogger("lexiredact")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            return

    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger scoped under the ``LexiRedact`` namespace.

    Args:
        name: Typically __name__ of the calling module. The "lexiredact."
              prefix is added automatically.

    Returns:
        A logging.Logger instance namespaced under lexiredact.
    """
    return logging.getLogger(f"lexiredact.{name}")
