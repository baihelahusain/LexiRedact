"""
LexiRedact — Privacy-preserving RAG ingestion middleware with dual-pipeline processing.

Import everything you need from here:
    from lexiredact import load_config, ProcessingResult, configure_logging
"""

from __future__ import annotations

from lexiredact.config.loader import load_config
from lexiredact.pipeline_api import LexiredactPipeline
from lexiredact.config.schema import LexiredactConfig
from lexiredact.exceptions import (
    LexiredactCacheError,
    LexiredactConfigError,
    LexiredactError,
    LexiredactInputError,
    LexiredactStorageError,
)
from lexiredact.app_logging import configure_logging, get_logger
from lexiredact.models.chunk import Chunk
from lexiredact.models.result import DetectedEntity, ProcessingResult

__version__ = "0.0.2"

__all__ = [
    "LexiredactConfig",
    "LexiredactPipeline",
    "load_config",
    "ProcessingResult",
    "DetectedEntity",
    "Chunk",
    "LexiredactError",
    "LexiredactConfigError",
    "LexiredactInputError",
    "LexiredactStorageError",
    "LexiredactCacheError",
    "configure_logging",
    "get_logger",
    "__version__",
]
