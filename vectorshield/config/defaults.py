"""
Safe default configuration for VectorShield.

These values enable out-of-the-box execution without requiring user configuration.
"""
from typing import List, Dict, Any


DEFAULT_CONFIG: Dict[str, Any] = {
    # PII Detection Settings
    "pii_entities": [
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "US_SSN",
        "LOCATION",
        "DATE_TIME",
        "MEDICAL_LICENSE",
        "US_PASSPORT",
    ],
    
    # Embedding Settings
    "embedding_model": "BAAI/bge-small-en-v1.5",  # Fast, lightweight, 384-dim
    "embedding_batch_size": 32,
    
    # Cache Settings
    "cache_backend": "memory",  # Options: "memory", "redis", "none"
    "cache_ttl": 3600,  # 1 hour
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    
    # Vector Store Settings
    "vectorstore_backend": "chroma",
    "vectorstore_path": "./vectorshield_data",
    "vectorstore_collection": "documents",
    
    # Processing Settings
    "parallel_processing": True,
    "max_batch_size": 1000,
    
    # Tracking Settings
    "tracking_enabled": False,
    "tracking_backend": "none",  # Options: "mlflow", "none"
    "mlflow_tracking_uri": "http://localhost:5000",
    "mlflow_experiment_name": "vectorshield",
    
    # Performance Settings
    "enable_async": True,
    "timeout_seconds": 30,
}


def get_default_config() -> Dict[str, Any]:
    """
    Get a copy of the default configuration.
    
    Returns:
        Dictionary with default configuration values
    """
    return DEFAULT_CONFIG.copy()


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and fill missing configuration values with defaults.
    
    Args:
        config: User-provided configuration
        
    Returns:
        Complete configuration with defaults filled in
        
    Raises:
        ValueError: If configuration contains invalid values
    """
    validated = get_default_config()
    validated.update(config)
    
    # Validation rules
    if validated["cache_ttl"] < 0:
        raise ValueError("cache_ttl must be non-negative")
    
    if validated["max_batch_size"] < 1:
        raise ValueError("max_batch_size must be at least 1")
    
    if validated["embedding_batch_size"] < 1:
        raise ValueError("embedding_batch_size must be at least 1")
    
    if validated["cache_backend"] not in ["memory", "redis", "none"]:
        raise ValueError(f"Invalid cache_backend: {validated['cache_backend']}")
    
    if validated["vectorstore_backend"] not in ["chroma", "custom"]:
        raise ValueError(f"Invalid vectorstore_backend: {validated['vectorstore_backend']}")
    
    if validated["tracking_backend"] not in ["mlflow", "none"]:
        raise ValueError(f"Invalid tracking_backend: {validated['tracking_backend']}")
    
    return validated
