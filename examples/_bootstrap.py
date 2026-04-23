"""Helpers for running examples from a source checkout."""

from pathlib import Path
import sys


def ensure_project_root() -> None:
    """Add the repository root to sys.path when examples run directly."""
    project_root = Path(__file__).resolve().parent.parent
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
