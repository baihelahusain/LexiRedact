# MLflow

LexiRedact does not currently include a first-class MLflow integration in the package API.

You can still log ingestion experiments from your application by recording:

- config values such as `pipeline_mode`, `embedder.model_name`, and `pii.score_threshold`
- aggregate latency from `ProcessingResult.latency_ms`
- privacy counts from `entities_detected`
- retrieval metrics from your evaluation harness

Example shape:

```python
import mlflow

with mlflow.start_run():
    results = pipeline.ingest(chunks)
    mlflow.log_param("pipeline_mode", config.pipeline_mode)
    mlflow.log_metric("chunks", len(results))
    mlflow.log_metric(
        "avg_latency_ms",
        sum(r.latency_ms for r in results) / max(len(results), 1),
    )
    mlflow.log_metric(
        "entities_detected",
        sum(len(r.entities_detected) for r in results),
    )
```

Keep MLflow code in your application layer so LexiRedact remains a focused ingestion middleware package.
