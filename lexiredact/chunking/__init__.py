"""
Document chunking module for LexiRedact.

Converts PDFs and large text documents into manageable chunks
suitable for embedding and PII detection.
"""

from .chunker import Chunk, DocumentChunker, ChunkingStrategy
from .json_exporter import JSONExporter
from .pdf_loader import PDFLoader

__all__ = [
    "Chunk",
    "DocumentChunker",
    "ChunkingStrategy",
    "PDFLoader",
    "JSONExporter",
]
