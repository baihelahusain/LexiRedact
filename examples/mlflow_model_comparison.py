"""
Compare multiple embedding models in MLflow using the same document set.

Run an MLflow server first, then execute this example to create one run per
model inside the same experiment.
"""
import asyncio
import importlib.util
from typing import List

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs


DOCUMENTS = [
    vs.Document(
        id="hr-1",
        text="Employee John Doe can be reached at john.doe@example.com for onboarding support.",
        metadata={"domain": "hr", "source": "employee_handbook"},
    ),
    vs.Document(
        id="legal-1",
        text="Contract owner Sarah Connor signed on 2026-01-15 and can be reached at sarah@example.com.",
        metadata={"domain": "legal", "source": "contracts"},
    ),
    vs.Document(
        id="support-1",
        text="Ticket owner Mike Ross can be called at 555-0101 to resolve customer escalations.",
        metadata={"domain": "support", "source": "ticketing"},
    ),
]


async def run_model(model_name: str) -> None:
    config = vs.load_config(
        config_dict={
            "embedding_model": model_name,
            "tracking_enabled": True,
            "tracking_backend": "mlflow",
            "mlflow_tracking_uri": "http://localhost:5000",
            "mlflow_experiment_name": "lexiredact-model-comparison",
            "mlflow_run_name": model_name.replace("/", "_"),
            "vectorstore_collection": model_name.replace("/", "_"),
            "vectorstore_path": ".tmp-build/mlflow_model_comparison_data",
        }
    )

    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()

    result = await pipeline.process_batch(DOCUMENTS)
    metrics = pipeline.get_metrics()

    print(f"Model: {model_name}")
    print(f"Processed: {result['total_processed']}")
    print(f"Avg latency: {metrics['performance']['avg_latency_ms']} ms")
    print(f"Privacy overhead: {metrics['performance']['privacy_overhead_percent']}%")
    print()

    await pipeline.shutdown()


async def main() -> None:
    if importlib.util.find_spec("mlflow") is None:
        print("This example requires mlflow. Install with: pip install mlflow")
        return

    models: List[str] = [
        "BAAI/bge-small-en-v1.5",
        "BAAI/bge-base-en-v1.5",
    ]

    for model_name in models:
        await run_model(model_name)


if __name__ == "__main__":
    asyncio.run(main())
