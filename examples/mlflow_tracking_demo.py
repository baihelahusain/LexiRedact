"""
MLflow Tracking Demo for LexiRedact.

What this shows:
- how to enable MLflow tracking
- how one run appears in MLflow
- how to compare two embedding models in the same experiment

Before running:
1. Start MLflow:
   mlflow server --host 127.0.0.1 --port 5000
2. Open the UI:
   http://127.0.0.1:5000
3. Run this script:
   python examples/mlflow_tracking_demo.py
"""
import asyncio
import importlib.util

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs


DOCUMENTS = [
    vs.Document(
        id="doc-1",
        text="John Doe can be reached at john.doe@example.com for onboarding support.",
        metadata={"domain": "hr", "source": "employee_handbook"},
    ),
    vs.Document(
        id="doc-2",
        text="Sarah Connor signed the contract on 2026-01-15 and can be reached at sarah@example.com.",
        metadata={"domain": "legal", "source": "contracts"},
    ),
    vs.Document(
        id="doc-3",
        text="Mike Ross can be called at 555-0101 to resolve customer escalations.",
        metadata={"domain": "support", "source": "ticketing"},
    ),
]


async def run_experiment(model_name: str, experiment_name: str) -> None:
    config = vs.load_config(
        config_dict={
            "embedding_model": model_name,
            "tracking_enabled": True,
            "tracking_backend": "mlflow",
            "mlflow_tracking_uri": "http://127.0.0.1:5000",
            "mlflow_experiment_name": experiment_name,
            "mlflow_run_name": model_name.replace("/", "_"),
            "mlflow_log_artifacts": True,
            "mlflow_log_storage_samples": 3,
            "vectorstore_collection": model_name.replace("/", "_"),
            "vectorstore_path": ".tmp-build/mlflow_tracking_data",
        }
    )

    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()

    result = await pipeline.process_batch(DOCUMENTS)
    metrics = pipeline.get_metrics()

    print("=" * 60)
    print(f"Model: {model_name}")
    print(f"Processed: {result['total_processed']}")
    print(f"Total Time: {result['total_time_seconds']}s")
    print(f"Avg Latency: {metrics['performance']['avg_latency_ms']} ms")
    print(f"Avg Embedding Time: {metrics['breakdown']['avg_embedding_ms']} ms")
    print(f"Privacy Overhead: {metrics['performance']['privacy_overhead_percent']}%")
    print(f"Cache Hit Rate: {metrics['caching']['cache_hit_rate']}")
    print("MLflow should now show:")
    print("- parameters for this run")
    print("- document and batch metrics")
    print("- run summary metrics")
    print("- lexiredact_run_summary.json artifact")

    await pipeline.shutdown()


async def main() -> None:
    if importlib.util.find_spec("mlflow") is None:
        print("This example requires mlflow. Install with: pip install mlflow")
        return

    experiment_name = "lexiredact-demo-tracking"

    print("Running MLflow demo experiment")
    print(f"Experiment: {experiment_name}")
    print("Open MLflow UI at http://127.0.0.1:5000")
    print()

    for model_name in [
        "BAAI/bge-small-en-v1.5",
        "BAAI/bge-base-en-v1.5",
    ]:
        await run_experiment(model_name, experiment_name)

    print()
    print("Done.")
    print("In MLflow, compare the two runs by:")
    print("- run name")
    print("- run_avg_latency_ms")
    print("- run_avg_embedding_ms")
    print("- run_success_rate")
    print("- run_privacy_overhead_percent")
    print("- lexiredact/lexiredact_run_summary.json artifact")


if __name__ == "__main__":
    asyncio.run(main())
