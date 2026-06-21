# Evaluation

The repository contains an `eval/` folder for local experiments, but it is not part of the packaged public API.

For user-facing evaluation, compare the three pipeline modes on your own retrieval set:

- `raw`: baseline quality, no privacy protection.
- `dual`: original-text embeddings with sanitized stored metadata.
- `preredacted`: sanitized-text embeddings and sanitized stored metadata.

## Suggested metrics

- Retrieval quality: recall@k, MRR, nDCG.
- Privacy: number of PII entities in stored metadata.
- Latency: `ProcessingResult.latency_ms` and `stage_latencies`.
- Cache behavior: `ProcessingResult.cache_hit`.

## Simple workflow

1. Build a small JSON chunk set.
2. Build query and expected-answer pairs.
3. Ingest the same chunks in each mode using different Chroma collections.
4. Embed each query with `query_embed()`.
5. Query the store and compute retrieval metrics.

See `examples/retrieval_metrics_demo.py` for a dependency-light scoring example.
