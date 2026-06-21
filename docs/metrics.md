# Metrics

Every successful `ingest()` call returns `ProcessingResult` objects.

Useful fields:

- `latency_ms`: average per-chunk pipeline latency.
- `stage_latencies`: per-stage timing breakdown.
- `entities_detected`: detected PII spans.
- `cache_hit`: whether Redis supplied the embedding.
- `embedding_stored`: whether the vector was written.
- `error`: chunk-level error message, if present.

Example:

```python
results = pipeline.ingest(chunks)

avg_latency = sum(r.latency_ms for r in results) / max(len(results), 1)
pii_count = sum(len(r.entities_detected) for r in results)
cache_hits = sum(1 for r in results if r.cache_hit)
```

For CLI ingestion, use:

```bash
lexiredact ingest --config lexiredact_config.yaml --input chunks.json --output results.json
```

The output JSON is generated from `ProcessingResult.to_dict()`.
