"""
LexiRedact - Privacy-Preserving RAG Middleware

A Python SDK for protecting PII in vector databases while maintaining
semantic search quality through intelligent embedding and redaction.

Key Features:
- Automatic PII detection and redaction using Microsoft Presidio
- Embedding generation from original text (Shadow Mode architecture)
- Only sanitized text stored in vector databases
- Redis caching for performance optimization
- Pluggable architecture via dependency injection
- Comprehensive metrics and tracking

Basic Usage:
    >>> import lexiredact as vs
    >>> 
    >>> # Create pipeline with defaults
    >>> pipeline = vs.IngestionPipeline()
    >>> await pipeline.initialize()
    >>> 
    >>> # Process documents
    >>> doc = vs.Document(id="1", text="Contact John at john@example.com")
    >>> result = await pipeline.process_document(doc)
    >>> 
    >>> print(result.clean_text)  # "Contact <PERSON> at <EMAIL_ADDRESS>"
    >>> print(result.pii_entities)  # ["PERSON", "EMAIL_ADDRESS"]
    >>> 
    >>> await pipeline.shutdown()

Custom Configuration:
    >>> from lexiredact import IngestionPipeline, load_config
    >>> 
    >>> config = load_config(config_dict={
    ...     "embedding_model": "BAAI/bge-base-en-v1.5",
    ...     "cache_backend": "redis",
    ...     "redis_host": "localhost"
    ... })
    >>> 
    >>> pipeline = IngestionPipeline(config=config)

Custom Components:
    >>> from lexiredact import IngestionPipeline
    >>> from lexiredact.interfaces import Embedder
    >>> 
    >>> class MyEmbedder(Embedder):
    ...     # Custom implementation
    ...     pass
    >>> 
    >>> pipeline = IngestionPipeline(embedder=MyEmbedder())
"""

__version__ = "0.1.0"

# Core pipeline
from .pipeline import IngestionPipeline, Document, ProcessedDocument

# Configuration
from .config import load_config, get_default_config, save_config_to_yaml

# Privacy components
from .privacy import PIIDetector, PIIRedactor, PIIPolicy

# Interfaces (for custom implementations)
from .interfaces import CacheBackend, Embedder, VectorStore, Tracker

# Default implementations
from .implementations import (
    MemoryCache,  
    RedisCache,
    GenericCache,
    FastEmbedEmbedder,
    GenericEmbedder,  
    ChromaVectorStore,
    GenericVectorStore, 
    MLflowTracker,
)

# Metrics
from .metrics import (
    MetricsCollector,
    AggregateStats,
    RetrievalAggregateStats,
    RetrievalMetricsEvaluator,
    RetrievalQueryMetrics,
)

# Utilities
from .utils import hash_text, generate_cache_key, Timer

__all__ = [
    # Version
    "__version__",
    
    # Core
    "IngestionPipeline",
    "Document",
    "ProcessedDocument",
    
    # Configuration
    "load_config",
    "get_default_config",
    "save_config_to_yaml",
    
    # Privacy
    "PIIDetector",
    "PIIRedactor",
    "PIIPolicy",
    
    # Interfaces
    "CacheBackend",
    "Embedder",
    "VectorStore",
    "Tracker",
    
    #custom models
    "GenericCache",
    "GenericEmbedder", 
    "GenericVectorStore",
    
    # Implementations
    "MemoryCache",
    "RedisCache",
    "FastEmbedEmbedder",
    "ChromaVectorStore",
    "MLflowTracker",
    
    # Metrics
    "MetricsCollector",
    "AggregateStats",
    "RetrievalAggregateStats",
    "RetrievalMetricsEvaluator",
    "RetrievalQueryMetrics",
    
    # Utils
    "hash_text",
    "generate_cache_key",
    "Timer",
]
