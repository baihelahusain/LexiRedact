"""
config/loader.py — Loads and validates LexiRedact configuration from various sources.

Accepts a plain dict, a file-system path (str or pathlib.Path), or a YAML file.
Pydantic validation errors are translated into LexiredactConfigError.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from lexiredact.config.schema import LexiredactConfig
from lexiredact.exceptions import LexiredactConfigError
from lexiredact.app_logging import get_logger

logger = get_logger(__name__)


def _validation_error_to_message(exc: ValidationError) -> str:
    lines: list[str] = ["Configuration validation failed:"]
    for error in exc.errors():
        loc = " -> ".join(str(p) for p in error["loc"]) if error["loc"] else "(root)"
        lines.append(f"  field '{loc}': {error['msg']} (got {error.get('input', '<unknown>')!r})")
    return "\n".join(lines)


def load_config(source: dict[str, Any] | str | Path) -> LexiredactConfig:
    """Load and validate a LexiredactConfig from a dict, str path, or Path.

    Raises:
        LexiredactConfigError: On missing file, YAML parse error, or validation failure.
    """
    raw: dict[str, Any]

    match source:
        case dict():
            raw = source
            logger.debug("Loading configuration from dict.")
        case str() | Path():
            path = Path(source)
            logger.debug("Loading configuration from file: %s", path)
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                raise LexiredactConfigError(
                    f"Configuration file not found: {path}",
                    context={"path": str(path)},
                ) from exc
            try:
                loaded = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise LexiredactConfigError(
                    f"Failed to parse YAML configuration file: {path}",
                    context={"path": str(path), "yaml_error": str(exc)},
                ) from exc
            if not isinstance(loaded, dict):
                raise LexiredactConfigError(
                    f"Config file must contain a YAML mapping at the top level: {path}",
                    context={"path": str(path), "got_type": type(loaded).__name__},
                )
            raw = loaded
        case _:
            raise LexiredactConfigError(
                "load_config() requires a dict, str, or Path as source.",
                context={"got_type": type(source).__name__},
            )

    try:
        config = LexiredactConfig(**raw)
    except ValidationError as exc:
        raise LexiredactConfigError(
            _validation_error_to_message(exc),
            context={"raw_keys": list(raw.keys())},
        ) from exc

    logger.debug("Configuration loaded. pipeline_mode=%s", config.pipeline_mode)
    return config
