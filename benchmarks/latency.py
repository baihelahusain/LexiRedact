"""
Latency Benchmark

Measures end-to-end latency for document processing.
Compares sequential vs parallel processing modes.
"""
import asyncio
import time
import statistics
import vectorshield as vs


async def benchmark_latency(num_documents: int = 100):
    """
    Run latency benchmark.
    
    Args:
        num_documents: Number of documents to process
    """
    print("=" * 60)
    print("VectorShield Latency Benchmark")
    print("=" * 60)
    print(f"Processing {num_documents} documents...")
    print()
    
    # Generate test documents
    documents = [
        vs.Document(
            id=f"doc_{i}",
            text=f"Contact person{i} at person{i}@email.com or call 555-{i:04d}",
            metadata={"index": i}
        )
        for i in range(num_documents)
    ]
    
    # Benchmark 1: Parallel processing (default)
    print("🔄 Test 1: Parallel Processing (Default)")
    config_parallel = vs.load_config(config_dict={
        "parallel_processing": True,
        "cache_backend": "memory"
    })
    
    pipeline_parallel = vs.IngestionPipeline(config=config_parallel)
    await pipeline_parallel.initialize()
    
    start = time.perf_counter()
    result_parallel = await pipeline_parallel.process_batch(documents)
    parallel_time = time.perf_counter() - start
    
    metrics_parallel = pipeline_parallel.get_metrics()
    
    print(f"   Total Time: {parallel_time:.3f}s")
    print(f"   Avg Latency: {metrics_parallel['performance']['avg_latency_ms']} ms/doc")
    print(f"   Throughput: {num_documents / parallel_time:.2f} docs/sec")
    print()
    
    await pipeline_parallel.shutdown()
    
    # Benchmark 2: Sequential processing
    print("🔄 Test 2: Sequential Processing")
    config_sequential = vs.load_config(config_dict={
        "parallel_processing": False,
        "cache_backend": "memory"
    })
    
    pipeline_sequential = vs.IngestionPipeline(config=config_sequential)
    await pipeline_sequential.initialize()
    
    start = time.perf_counter()
    result_sequential = await pipeline_sequential.process_batch(documents)
    sequential_time = time.perf_counter() - start
    
    metrics_sequential = pipeline_sequential.get_metrics()
    
    print(f"   Total Time: {sequential_time:.3f}s")
    print(f"   Avg Latency: {metrics_sequential['performance']['avg_latency_ms']} ms/doc")
    print(f"   Throughput: {num_documents / sequential_time:.2f} docs/sec")
    print()
    
    await pipeline_sequential.shutdown()
    
    # Compare
    speedup = sequential_time / parallel_time
    print("📊 Comparison:")
    print(f"   Parallel Time: {parallel_time:.3f}s")
    print(f"   Sequential Time: {sequential_time:.3f}s")
    print(f"   Speedup: {speedup:.2f}x")
    print()
    
    # Latency distribution
    print("📈 Latency Distribution (Parallel Mode):")
    latencies = [m.total_time_ms for m in pipeline_parallel.metrics.metrics]
    if latencies:
        print(f"   Min: {min(latencies):.2f} ms")
        print(f"   Median: {statistics.median(latencies):.2f} ms")
        print(f"   Mean: {statistics.mean(latencies):.2f} ms")
        print(f"   Max: {max(latencies):.2f} ms")
        print(f"   Std Dev: {statistics.stdev(latencies):.2f} ms")
    print()
    
    print("💡 Key Insights:")
    print("   - Parallel processing runs PII detection + embedding concurrently")
    print("   - This reduces per-document latency significantly")
    print("   - Batch processing amortizes overhead across documents")
    print()


if __name__ == "__main__":
    asyncio.run(benchmark_latency(num_documents=50))