# Evaluation Guide

This document describes how to evaluate VectorShield for correctness, privacy behavior, and performance.

## Evaluation Dimensions

1. Privacy correctness
2. Ingestion reliability
3. Latency and throughput
4. Cache effectiveness
5. Retrieval quality impact

## 1. Privacy Correctness

Goal:
- Verify that sensitive entities are detected and redacted before storage.

Checks:
- Process documents with known PII.
- Assert sanitized output contains placeholders instead of raw values.
- Assert returned `pii_found` includes expected entity labels.

Example test cases:
- Email and phone in one sentence.
- Mixed identifiers across metadata-heavy documents.
- No-PII text to ensure low false positives.

## 2. Storage Safety

Goal:
- Confirm vector store receives sanitized text only.

Method:
- Process sample documents.
- Query vector store records (or use store inspection hooks).
- Validate no raw sensitive values appear in persisted `documents`.

## 3. Pipeline Reliability

Goal:
- Ensure stable behavior under normal and edge conditions.

Checks:
- `initialize()` and `shutdown()` lifecycle.
- Single document and batch processing.
- Batch size limit handling.
- Component failure path returns `status="failed"` without crashing process.

## 4. Performance Benchmarks

Use provided scripts:

- `benchmarks/latency.py`
- `benchmarks/cache_effect.py`
- `benchmarks/embedding_compare.py`

Measure:
- Avg/P95 latency per document
- Batch completion time
- Cache hit and miss counts
- End-to-end throughput

## 5. Cache Impact Validation

Recommended experiment:

1. Run repeated documents with empty cache.
2. Re-run same workload with warm cache.
3. Compare:
   - total time
   - hit rate
   - PII detection stage latency

Expected:
- Significant latency reduction for repeated content.

## 6. Retrieval Quality Sanity Check

Because embeddings are computed from original text, semantic fidelity should remain strong.

Suggested checks:
- Run representative queries before and after privacy layer integration.
- Compare overlap of top-k results and relevance quality.

## 7. Reporting Template

For each run, capture:

- Commit SHA
- Config snapshot
- Dataset profile
- Runtime environment
- Key metrics:
  - success rate
  - avg latency
  - cache hit rate
  - PII entities redacted

This makes regressions detectable during releases.
