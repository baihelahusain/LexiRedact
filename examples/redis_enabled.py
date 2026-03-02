"""
Redis-Enabled Example

Demonstrates VectorShield with Redis caching for production deployments.
Redis provides distributed caching across multiple instances.

Prerequisites:
    - Redis server running on localhost:6379
    - Install: pip install redis
    
To start Redis (Docker):
    docker run -d -p 6379:6379 redis:latest
"""
import asyncio
import vectorshield as vs


async def main():
    """Redis caching example."""
    
    print("=" * 60)
    print("VectorShield - Redis Caching Example")
    print("=" * 60)
    print()
    
    # Configuration with Redis caching
    config = vs.load_config(config_dict={
        "cache_backend": "redis",
        "redis_host": "localhost",
        "redis_port": 6379,
        "cache_ttl": 3600,  # 1 hour cache
    })
    
    print("📋 Configuration:")
    print(f"   Cache Backend: {config['cache_backend']}")
    print(f"   Redis Host: {config['redis_host']}:{config['redis_port']}")
    print(f"   Cache TTL: {config['cache_ttl']}s")
    print()
    
    # Create pipeline with Redis
    pipeline = vs.IngestionPipeline(config=config)
    await pipeline.initialize()
    print()
    
    # Test documents (some will have duplicates to test caching)
    documents = [
        vs.Document(id="1", text="Contact Alice at alice@email.com"),
        vs.Document(id="2", text="Call Bob at 555-1234"),
        vs.Document(id="3", text="Contact Alice at alice@email.com"),  # Duplicate
        vs.Document(id="4", text="Call Bob at 555-1234"),  # Duplicate
        vs.Document(id="5", text="New document without duplicates"),
    ]
    
    # First run - cache misses
    print("🔄 First run (cache misses expected)...")
    result1 = await pipeline.process_batch(documents)
    metrics1 = pipeline.get_metrics()
    
    print(f"\n📊 First Run Metrics:")
    print(f"   Total Processed: {result1['total_processed']}")
    print(f"   Time: {result1['total_time_seconds']}s")
    print(f"   Cache Hits: {metrics1['caching']['cache_hits']}")
    print(f"   Cache Misses: {metrics1['caching']['cache_misses']}")
    print(f"   Cache Hit Rate: {metrics1['caching']['cache_hit_rate']}")
    print()
    
    # Reset metrics for second run
    pipeline.reset_metrics()
    
    # Second run - cache hits expected for duplicates
    print("🔄 Second run (cache hits expected for duplicates)...")
    result2 = await pipeline.process_batch(documents)
    metrics2 = pipeline.get_metrics()
    
    print(f"\n📊 Second Run Metrics:")
    print(f"   Total Processed: {result2['total_processed']}")
    print(f"   Time: {result2['total_time_seconds']}s")
    print(f"   Cache Hits: {metrics2['caching']['cache_hits']}")
    print(f"   Cache Misses: {metrics2['caching']['cache_misses']}")
    print(f"   Cache Hit Rate: {metrics2['caching']['cache_hit_rate']}")
    print()
    
    # Compare performance
    speedup = result1['total_time_seconds'] / result2['total_time_seconds'] if result2['total_time_seconds'] > 0 else 1.0
    print(f"⚡ Performance Improvement:")
    print(f"   First Run Time: {result1['total_time_seconds']:.3f}s")
    print(f"   Second Run Time: {result2['total_time_seconds']:.3f}s")
    print(f"   Speedup: {speedup:.2f}x")
    print()
    
    print("💡 Key Insight:")
    print("   Redis caching significantly reduces latency for repeated content.")
    print("   PII detection results are cached, but embeddings are still generated")
    print("   from original text to maintain semantic quality.")
    print()
    
    # Cleanup
    await pipeline.shutdown()
    print("✅ Redis caching example complete!")


if __name__ == "__main__":
    asyncio.run(main())