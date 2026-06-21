"""Log LexiRedact ingestion metrics to MLflow from application code."""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401


def log_results_to_mlflow(results, config) -> None:
    import mlflow

    with mlflow.start_run():
        mlflow.log_param("pipeline_mode", config.pipeline_mode)
        mlflow.log_param("embedder_model", config.embedder.model_name)
        mlflow.log_metric("chunks", len(results))
        mlflow.log_metric(
            "avg_latency_ms",
            sum(result.latency_ms for result in results) / max(len(results), 1),
        )
        mlflow.log_metric(
            "entities_detected",
            sum(len(result.entities_detected) for result in results),
        )


print(
    "Call log_results_to_mlflow(results, config) after pipeline.ingest(). "
    "Install mlflow separately if you use this pattern."
)
