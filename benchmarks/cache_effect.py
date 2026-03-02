"""
Cache Effect Benchmark

Measures the performance impact of Redis caching on repeated content.
Demonstrates cache hit/miss patterns and latency improvements.
"""
import asyncio
import time
import vectorshield as vs


async def benchmark_cache_effect():
    """Benchmark cache effectiveness."""
    
    print("=" * 60)
    print("VectorShield Cache Effect Benchmark")
    print("=" * 60)
    print()
    
    # Test documents with intentional duplicates
    unique_texts = [
        "Contact Alice Smith at alice@company.com",
        "Call Bob Johnson at 555-1234",
        "Patient record for John Doe, SSN: 123-45-6789",
        "Email sarah@example.com for more information",
        "Credit card ending in 4567 was charged",
    ]
    
    # Create dataset with 50% duplicates
    documents = []
    for i in range(50):
        text = unique_texts[i % len(unique_texts)]  # Repeat texts
        documents.append(vs.Document(id=f"doc_{i}", text=text))
    
    print(f"📊 Dataset:")
    print(f"   Total Documents: {len(documents)}")
    print(f"   Unique Texts: {len(unique_texts)}")
    print(f"   Expected Cache Hit Rate: ~{((len(documents) - len(unique_texts)) / len(documents)) * 100:.1f}%")
    print()
    
    # Test with memory cache
    print("🔄 Test 1: Memory Cache")
    config_memory = vs.load_config(config_dict={"cache_backend": "memory"})
    pipeline_memory = vs.IngestionPipeline(config=config_memory)
    await pipeline_memory.initialize()
    
    start = time.perf_counter()
    result_memory = await pipeline_memory.process_batch(documents)
    memory_time = time.perf_counter() - start
    
    metrics_memory = pipeline_memory.get_metrics()
    
    print(f"   Time: {memory_time:.3f}s")
    print(f"   Cache Hits: {metrics_memory['caching']['cache_hits']}")
    print(f"   Cache Misses: {metrics_memory['caching']['cache_misses']}")
    print(f"   Cache Hit Rate: {metrics_memory['caching']['cache_hit_rate']}")
    print(f"   Avg Latency: {metrics_memory['performance']['avg_latency_ms']} ms")
    print()
    
    await pipeline_memory.shutdown()
    
    # Test without cache (baseline)
    print("🔄 Test 2: No Cache (Baseline)")
    config_none = vs.load_config(config_dict={"cache_backend": "none"})
    pipeline_none = vs.IngestionPipeline(config=config_none)
    await pipeline_none.initialize()
    
    start = time.perf_counter()
    result_none = await pipeline_none.process_batch(documents)
    none_time = time.perf_counter() - start
    
    metrics_none = pipeline_none.get_metrics()
    
    print(f"   Time: {none_time:.3f}s")
    print(f"   Avg Latency: {metrics_none['performance']['avg_latency_ms']} ms")
    print()
    
    await pipeline_none.shutdown()
    
    # Compare
    speedup = none_time / memory_time
    latency_reduction = (
        float(metrics_none['performance']['avg_latency_ms'].split()[0]) -
        float(metrics_memory['performance']['avg_latency_ms'].split()[0])
    )
    
    print("📊 Cache Impact Analysis:")
    print(f"   With Cache: {memory_time:.3f}s")
    print(f"   Without Cache: {none_time:.3f}s")
    print(f"   Speedup: {speedup:.2f}x")
    print(f"   Latency Reduction: {latency_reduction:.2f} ms per document")
    print()
    
    # Break down time savings
    cache_hits = int(metrics_memory['caching']['cache_hits'])
    time_saved = (none_time - memory_time)
    time_saved_per_hit = time_saved / cache_hits if cache_hits > 0 else 0
    
    print("💰 Time Savings Breakdown:")
    print(f"   Total Time Saved: {time_saved:.3f}s")
    print(f"   Time Saved per Cache Hit: {time_saved_per_hit * 1000:.2f} ms")
    print(f"   Cache Hits: {cache_hits}")
    print()
    
    print("💡 Key Insights:")
    print("   - Caching PII detection results significantly reduces repeated work")
    print("   - Higher cache hit rates = better performance")
    print("   - Redis cache enables sharing across multiple instances")
    print("   - Embeddings are still generated from original text (not cached)")
    print()
    
    # Privacy overhead comparison
    pii_overhead_cached = float(metrics_memory['performance']['privacy_overhead_percent'].rstrip('%'))
    pii_overhead_uncached = float(metrics_none['performance']['privacy_overhead_percent'].rstrip('%'))
    
    print("🔒 Privacy Overhead:")
    print(f"   With Cache: {pii_overhead_cached:.2f}%")
    print(f"   Without Cache: {pii_overhead_uncached:.2f}%")
    print(f"   Reduction: {pii_overhead_uncached - pii_overhead_cached:.2f}%")
    print()


if __name__ == "__main__":
    asyncio.run(benchmark_cache_effect())