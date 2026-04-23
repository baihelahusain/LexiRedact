# MLflow Guide

This guide explains how to use LexiRedact with MLflow so you can compare different embedding models and inspect performance across runs.

## 1. What MLflow Tracks in LexiRedact

When MLflow tracking is enabled, LexiRedact logs:

- run parameters such as embedding model, cache backend, vector store, Presidio settings, and batch limits
- per-document metrics such as latency, cache hits, PII counts, and stage timings
- per-batch metrics such as throughput, batch size, batch failures, and PII counts
- run-level summary metrics such as average latency, success rate, cache hit rate, privacy overhead, and total PII entities found
- a JSON artifact with config, summary metrics, recent document metrics, storage info, and a storage sample

This makes MLflow useful for model comparison instead of only showing a few isolated points.

## 2. Install MLflow

```bash
pip install mlflow
```

## 3. Start an MLflow Server

Local quick start:

```bash
mlflow server --host 127.0.0.1 --port 5000
```

Then open the UI at:

```text
http://127.0.0.1:5000
```

## 4. Enable MLflow in LexiRedact

```python
import lexiredact as vs

config = vs.load_config(config_dict={
    "tracking_enabled": True,
    "tracking_backend": "mlflow",
    "mlflow_tracking_uri": "http://localhost:5000",
    "mlflow_experiment_name": "lexiredact",
    "mlflow_run_name": "bge-small-baseline",
})

pipeline = vs.IngestionPipeline(config=config)
```

Relevant config keys:

- `tracking_enabled`
- `tracking_backend`
- `mlflow_tracking_uri`
- `mlflow_experiment_name`
- `mlflow_run_name`
- `mlflow_log_artifacts`
- `mlflow_log_storage_samples`

## 5. Minimal Example

```python
import asyncio
import lexiredact as vs


async def main():
    config = vs.load_config(config_dict={
        "tracking_enabled": True,
        "tracking_backend": "mlflow",
        "mlflow_tracking_uri": "http://localhost:5000",
        "mlflow_experiment_name": "lexiredact-demo",
        "mlflow_run_name": "demo-run-1",
    })

    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()

    docs = [
        vs.Document(id="1", text="John Doe can be reached at john@example.com"),
        vs.Document(id="2", text="Call Sarah at 555-123-4567"),
    ]

    await pipeline.process_batch(docs)
    await pipeline.shutdown()


asyncio.run(main())
```

After the run finishes, open MLflow and inspect:

- Parameters
- Metrics
- Artifacts

## 6. Compare Different Models

The most useful MLflow workflow is one run per embedding model under the same experiment.

Example:

```python
import asyncio
import lexiredact as vs


DOCUMENTS = [
    vs.Document(id="1", text="John Doe can be reached at john@example.com"),
    vs.Document(id="2", text="Call Sarah at 555-123-4567"),
]


async def run_model(model_name: str):
    config = vs.load_config(config_dict={
        "embedding_model": model_name,
        "tracking_enabled": True,
        "tracking_backend": "mlflow",
        "mlflow_tracking_uri": "http://localhost:5000",
        "mlflow_experiment_name": "lexiredact-model-comparison",
        "mlflow_run_name": model_name.replace("/", "_"),
        "vectorstore_collection": model_name.replace("/", "_"),
    })

    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()
    await pipeline.process_batch(DOCUMENTS)
    await pipeline.shutdown()


async def main():
    for model_name in [
        "BAAI/bge-small-en-v1.5",
        "BAAI/bge-base-en-v1.5",
    ]:
        await run_model(model_name)


asyncio.run(main())
```

There is also a runnable example in:

- `examples/mlflow_model_comparison.py`

## 7. What to Compare in MLflow

Useful metrics for comparing embedding models:

- `run_avg_latency_ms`
- `run_avg_embedding_ms`
- `run_success_rate`
- `run_privacy_overhead_percent`
- `run_total_pii_entities`
- `batch_throughput_docs_per_sec`

Interpretation:

- lower `run_avg_embedding_ms` is usually better for speed
- lower `run_avg_latency_ms` indicates faster end-to-end ingestion
- stable `run_success_rate` matters more than pure speed
- `run_privacy_overhead_percent` helps you understand how much time PII handling adds relative to the total

## 8. Artifacts Logged to MLflow

LexiRedact logs a JSON artifact named:

- `lexiredact/lexiredact_run_summary.json`

It contains:

- full run config
- aggregate metrics summary
- recent document-level metrics
- storage information
- a small storage sample

This is useful when you want to inspect one run in detail instead of only looking at scalar metrics.

## 9. Recommended MLflow Setup for Experiments

For clean comparisons:

- use one experiment per use case or dataset
- use one run per model
- keep the same document set across runs
- change only one major variable at a time
- use `mlflow_run_name` to make the UI readable
- use a separate `vectorstore_collection` per model run so stored data does not mix

## 10. Configuration Reference

MLflow-related config values:

```yaml
tracking_enabled: true
tracking_backend: mlflow
mlflow_tracking_uri: http://localhost:5000
mlflow_experiment_name: lexiredact
mlflow_run_name: bge-small-baseline
mlflow_log_artifacts: true
mlflow_log_storage_samples: 5
```

## 11. Common Problems

### Nothing shows up in MLflow

Check:

- `tracking_enabled` is `true`
- `tracking_backend` is `mlflow`
- the MLflow server is running
- the URI matches the running server
- `await pipeline.shutdown()` is called so summary metrics and artifacts are flushed

### Runs are hard to compare

Fix:

- keep the same experiment name
- set a clear `mlflow_run_name`
- use the same input dataset
- avoid changing cache, chunking, and vector store settings at the same time as the embedding model

### Artifact logging feels too noisy

Set:

```python
config = vs.load_config(config_dict={
    "mlflow_log_artifacts": False,
})
```

Or reduce storage samples:

```python
config = vs.load_config(config_dict={
    "mlflow_log_storage_samples": 2,
})
```

## 12. Privacy Notes

MLflow should be treated as part of your observability surface.

Keep these rules:

- do not log raw PII in custom tracker params or artifacts
- review metadata before storing or tracking it
- remember that storage samples and metrics artifacts may contain sanitized text and metadata

## 13. Related Docs

- `docs/user_guide.md`
- `docs/configuration.md`
- `docs/integrations.md`
