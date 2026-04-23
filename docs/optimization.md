# Optimization Guide

This guide focuses on practical performance tuning for LexiRedact.

## 1. Enable Parallel Processing

Use:

```yaml
parallel_processing: true
```

This overlaps PII detection and embedding generation on cache misses.
It is the biggest default latency win for mixed workloads.

## 2. Use Redis for Multi-Instance Deployments

Use:

```yaml
cache_backend: redis
redis_host: localhost
redis_port: 6379
cache_ttl: 3600
```

Why:

- Memory cache is per-process.
- Redis allows shared cache hits across workers/pods.
- Lower repeat processing latency.

## 3. Tune Cache TTL by Data Volatility

- Higher TTL:
  - Better hit rate
  - Lower repeated compute
- Lower TTL:
  - Fresher results if policies/entities change frequently

Start with `cache_ttl: 3600` and adjust from observed hit rate.

## 4. Select Embedding Model by Throughput Target

`BAAI/bge-small-en-v1.5` is the default for speed/quality balance.

When experimenting with larger models:

- Measure latency and cost impact.
- Validate retrieval quality gains before rollout.

## 5. Tune Batch Size

Relevant settings:

- `embedding_batch_size`
- `max_batch_size`

Guidance:

- Increase cautiously to improve throughput.
- Watch memory pressure and tail latency.

## 6. Keep Vector Store Locality in Mind

For Chroma:

- Put `vectorstore_path` on fast local disk.
- Avoid network-mounted slow volumes for latency-sensitive workloads.

## 7. Disable Tracking Unless Needed

If metrics backend is not required:

```yaml
tracking_enabled: false
tracking_backend: none
```

This avoids external logging overhead in hot paths.

## 8. Benchmark Regularly

Use repository scripts:

- `benchmarks/latency.py`
- `benchmarks/cache_effect.py`
- `benchmarks/embedding_compare.py`

Track:

- P50/P95 ingestion latency
- Cache hit rate
- Success rate
- Documents per second

## 9. Suggested Production Baseline

```yaml
parallel_processing: true
cache_backend: redis
cache_ttl: 3600
vectorstore_backend: chroma
vectorstore_path: ./lexiredact_data
tracking_enabled: false
max_batch_size: 1000
embedding_batch_size: 32
timeout_seconds: 30
```

## 10. Failure and Stability Tuning

- Keep timeouts conservative for upstream model calls.
- Use health checks for cache and vector store services.
- Alert on sharp drops in cache hit rate or increases in failed documents.
