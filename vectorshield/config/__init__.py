"""
Configuration module for VectorShield.

Provides safe defaults and configuration loading utilities.
"""

from .defaults import DEFAULT_CONFIG, get_default_config, validate_config
from .loader import load_config, save_config_to_yaml

__all__ = [
    "DEFAULT_CONFIG",
    "get_default_config",
    "validate_config",
    "load_config",
    "save_config_to_yaml",
]