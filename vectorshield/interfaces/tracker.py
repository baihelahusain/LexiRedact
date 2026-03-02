"""
Abstract tracker interface for VectorShield.

Trackers record metrics, experiments, and performance data.
Useful for monitoring and optimization analysis.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Tracker(ABC):
    """Abstract interface for metrics and experiment tracking."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to tracking backend."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connection and flush pending data."""
        pass
    
    @abstractmethod
    async def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """
        Log a single metric value.
        
        Args:
            key: Metric name (e.g., 'latency_ms', 'cache_hit_rate')
            value: Metric value
            step: Optional step/iteration number
        """
        pass
    
    @abstractmethod
    async def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """
        Log multiple metrics at once.
        
        Args:
            metrics: Dictionary of metric name -> value
            step: Optional step/iteration number
        """
        pass
    
    @abstractmethod
    async def log_param(self, key: str, value: Any) -> None:
        """
        Log a configuration parameter.
        
        Args:
            key: Parameter name (e.g., 'embedding_model', 'batch_size')
            value: Parameter value
        """
        pass
    
    @abstractmethod
    async def log_artifact(self, file_path: str, artifact_path: Optional[str] = None) -> None:
        """
        Log a file artifact.
        
        Args:
            file_path: Path to file to log
            artifact_path: Optional path within artifact store
        """
        pass