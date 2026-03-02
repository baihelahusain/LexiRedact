"""
Core ingestion pipeline for VectorShield.
"""

from .ingest import IngestionPipeline, Document, ProcessedDocument

__all__ = [
    "IngestionPipeline",
    "Document",
    "ProcessedDocument",
]