"""
LexiRedact quickstart example.

Demonstrates the simplest usage with default settings.
"""

import asyncio
from pathlib import Path

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as lr


async def main() -> None:
    print("=" * 60)
    print("LexiRedact Quickstart Example")
    print("=" * 60)
    print()

    print("Creating pipeline with default configuration...")
    config = lr.load_config(
        config_dict={
            "vectorstore_path": str(Path(".tmp-build") / "quickstart_data"),
            "vectorstore_collection": "quickstart_documents",
            "mlflow_log_artifacts": False,
        }
    )
    pipeline = lr.IngestionPipeline(config=config)
    await pipeline.initialize()
    print()

    print("Processing documents with PII...")
    documents = [
        lr.Document(
            id="doc1",
            text="Contact John Smith at john.smith@email.com or call 555-123-4567",
            metadata={"source": "customer_service"},
        ),
        lr.Document(
            id="doc2",
            text="Patient Sarah Johnson, DOB: 01/15/1985, SSN: 457-55-5462",
            metadata={"source": "medical_records"},
        ),
        lr.Document(
            id="doc3",
            text="The product launch is scheduled for next quarter in New York",
            metadata={"source": "internal_memo"},
        ),
    ]

    result = await pipeline.process_batch(documents)

    print("\nBatch Results:")
    print(f"   Total Processed: {result['total_processed']}")
    print(f"   Total Time: {result['total_time_seconds']}s")
    print()

    for doc_result in result["results"]:
        print(f"Document: {doc_result['id']}")
        print(f"   Status: {doc_result['status']}")
        print(f"   Original: {doc_result['original_preview']}")
        print(f"   Sanitized: {doc_result['clean_text']}")
        print(f"   PII Found: {doc_result['pii_found']}")
        print(f"   Embedding Preview: {doc_result['vector_preview']}")
        print()

    metrics = pipeline.get_metrics()
    print("Performance Metrics:")
    print(f"   Documents Processed: {metrics['overview']['total_documents']}")
    print(f"   Success Rate: {metrics['overview']['success_rate']}")
    print(f"   PII Entities Redacted: {metrics['privacy']['total_pii_entities_redacted']}")
    print(f"   Unique PII Types: {metrics['privacy']['unique_pii_types']}")
    print(f"   Average Latency: {metrics['performance']['avg_latency_ms']} ms")
    print(f"   Privacy Overhead: {metrics['performance']['privacy_overhead_percent']}")
    print(f"   Cache Hit Rate: {metrics['caching']['cache_hit_rate']}")
    print()

    await pipeline.shutdown()
    print("Example complete!")


if __name__ == "__main__":
    asyncio.run(main())
