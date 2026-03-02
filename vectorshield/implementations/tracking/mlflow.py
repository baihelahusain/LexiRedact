"""
MLflow tracking implementation for VectorShield.

Optional experiment tracking for performance monitoring.
Requires: pip install mlflow
"""
from typing import Dict, Any, Optional
from ...interfaces import Tracker

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class MLflowTracker(Tracker):
    """
    MLflow-based experiment tracking.
    
    Records metrics, parameters, and artifacts for analysis.
    Useful for optimization and performance monitoring.
    """
    
    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "vectorshield"
    ):
        """
        Initialize MLflow tracker.
        
        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: Experiment name
            
        Raises:
            ImportError: If mlflow is not installed
        """
        if not MLFLOW_AVAILABLE:
            raise ImportError(
                "MLflow support requires the mlflow package. "
                "Install with: pip install mlflow"
            )
        
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.run_id: Optional[str] = None
    
    async def connect(self) -> None:
        """Initialize MLflow tracking."""
        mlflow.set_tracking_uri(self.tracking_uri)
        
        # Create or get experiment
        try:
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if experiment is None:
                experiment_id = mlflow.create_experiment(self.experiment_name)
            else:
                experiment_id = experiment.experiment_id
            
            mlflow.set_experiment(experiment_id=experiment_id)
            
            # Start a new run
            run = mlflow.start_run()
            self.run_id = run.info.run_id
            
            print(f"✅ MLflow tracking started")
            print(f"   Experiment: {self.experiment_name}")
            print(f"   Run ID: {self.run_id}")
        except Exception as e:
            print(f"⚠️  MLflow connection failed: {e}")
            print("   Tracking will be disabled")
    
    async def close(self) -> None:
        """End MLflow run."""
        if self.run_id:
            mlflow.end_run()
            self.run_id = None
    
    async def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """
        Log a metric to MLflow.
        
        Args:
            key: Metric name
            value: Metric value
            step: Optional step number
        """
        if not self.run_id:
            return
        
        try:
            mlflow.log_metric(key, value, step=step)
        except Exception as e:
            print(f"MLflow log_metric error: {e}")
    
    async def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """
        Log multiple metrics to MLflow.
        
        Args:
            metrics: Dictionary of metric name -> value
            step: Optional step number
        """
        if not self.run_id:
            return
        
        try:
            mlflow.log_metrics(metrics, step=step)
        except Exception as e:
            print(f"MLflow log_metrics error: {e}")
    
    async def log_param(self, key: str, value: Any) -> None:
        """
        Log a parameter to MLflow.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        if not self.run_id:
            return
        
        try:
            mlflow.log_param(key, value)
        except Exception as e:
            print(f"MLflow log_param error: {e}")
    
    async def log_artifact(self, file_path: str, artifact_path: Optional[str] = None) -> None:
        """
        Log an artifact to MLflow.
        
        Args:
            file_path: Path to file
            artifact_path: Optional path in artifact store
        """
        if not self.run_id:
            return
        
        try:
            mlflow.log_artifact(file_path, artifact_path=artifact_path)
        except Exception as e:
            print(f"MLflow log_artifact error: {e}")


class NoOpTracker(Tracker):
    """
    No-operation tracker (disables tracking).
    
    Used when tracking is explicitly disabled.
    """
    
    async def connect(self) -> None:
        pass
    
    async def close(self) -> None:
        pass
    
    async def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        pass
    
    async def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        pass
    
    async def log_param(self, key: str, value: Any) -> None:
        pass
    
    async def log_artifact(self, file_path: str, artifact_path: Optional[str] = None) -> None:
        pass