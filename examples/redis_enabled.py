"""
Redis-Enabled Example

Demonstrates LexiRedact with Redis caching for production deployments.
Redis provides distributed caching across multiple instances.

Prerequisites:
    - Redis server running on localhost:6379
    - Install: pip install redis

To start Redis (Docker):
    docker run -d -p 6379:6379 redis:latest
"""

import asyncio
import socket

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs


def redis_ready(host: str = "localhost", port: int = 6379) -> bool:
    """Return True when Redis is installed and reachable."""
    try:
        import redis.asyncio  # noqa: F401
    except ImportError:
        print("This example requires the redis package. Install with: pip install redis")
        return False

    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        print(f"Redis server is not reachable at {host}:{port}. Start Redis and retry.")
        return False


async def main() -> None:
    """Redis caching example."""
    if not redis_ready():
        return

    print("=" * 60)
    print("LexiRedact - Redis Caching Example")
    print("=" * 60)
    print()

    config = vs.load_config(
        config_dict={
            "cache_backend": "redis",
            "redis_host": "localhost",
            "redis_port": 6379,
            "cache_ttl": 3600,
            "vectorstore_path": str(".tmp-build/redis_data"),
            "vectorstore_collection": "redis_demo_documents",
            "mlflow_log_artifacts": False,
        }
    )

    print("Configuration:")
    print(f"   Cache Backend: {config['cache_backend']}")
    print(f"   Redis Host: {config['redis_host']}:{config['redis_port']}")
    print(f"   Cache TTL: {config['cache_ttl']}s")
    print()

    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()
    print()

    documents = [
        vs.Document(id="1", text="Contact Alice at alice@email.com"),
        vs.Document(id="2", text="Call Bob at 555-1234"),
        vs.Document(id="3", text="Contact Alice at alice@email.com"),
        vs.Document(id="4", text="Call Bob at 555-1234"),
        vs.Document(id="5", text="New document without duplicates"),
    ]

    print("First run (cache misses expected)...")
    result1 = await pipeline.process_batch(documents)
    metrics1 = pipeline.get_metrics()

    print("\nFirst Run Metrics:")
    print(f"   Total Processed: {result1['total_processed']}")
    print(f"   Time: {result1['total_time_seconds']}s")
    print(f"   Cache Hits: {metrics1['caching']['cache_hits']}")
    print(f"   Cache Misses: {metrics1['caching']['cache_misses']}")
    print(f"   Cache Hit Rate: {metrics1['caching']['cache_hit_rate']}")
    print()

    pipeline.reset_metrics()

    print("Second run (cache hits expected for duplicates)...")
    result2 = await pipeline.process_batch(documents)
    metrics2 = pipeline.get_metrics()

    print("\nSecond Run Metrics:")
    print(f"   Total Processed: {result2['total_processed']}")
    print(f"   Time: {result2['total_time_seconds']}s")
    print(f"   Cache Hits: {metrics2['caching']['cache_hits']}")
    print(f"   Cache Misses: {metrics2['caching']['cache_misses']}")
    print(f"   Cache Hit Rate: {metrics2['caching']['cache_hit_rate']}")
    print()

    speedup = (
        result1["total_time_seconds"] / result2["total_time_seconds"]
        if result2["total_time_seconds"] > 0
        else 1.0
    )
    print("Performance Improvement:")
    print(f"   First Run Time: {result1['total_time_seconds']:.3f}s")
    print(f"   Second Run Time: {result2['total_time_seconds']:.3f}s")
    print(f"   Speedup: {speedup:.2f}x")
    print()

    print("Key Insight:")
    print("   Redis caching significantly reduces latency for repeated content.")
    print("   PII detection results are cached, but embeddings are still generated")
    print("   from original text to maintain semantic quality.")
    print()

    await pipeline.shutdown()
    print("Redis caching example complete!")


if __name__ == "__main__":
    asyncio.run(main())
