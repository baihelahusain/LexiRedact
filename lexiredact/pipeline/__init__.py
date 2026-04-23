"""
Core ingestion pipeline for LexiRedact.
"""

from .ingest import IngestionPipeline, Document, ProcessedDocument

__all__ = [
    "IngestionPipeline",
    "Document",
    "ProcessedDocument",
]