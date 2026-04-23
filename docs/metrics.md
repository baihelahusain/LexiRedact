# Metrics Guide

LexiRedact focuses on PII-safe ingestion first. The built-in metrics module now covers two separate needs:

- ingestion metrics for latency, privacy, caching, and throughput
- retrieval evaluation metrics for comparing embedding or storage choices

## Ingestion Metrics

`pipeline.get_metrics()` returns aggregate operational metrics collected during document processing.

It includes:

- overview totals and success rate
- privacy counts such as total detected entity types
- performance timings for redaction, embedding, and storage
- cache hit and miss counts

This is useful for validating that privacy protection is working without creating an unacceptable latency cost.

## Retrieval Evaluation Metrics

The retrieval evaluator is intentionally standalone in `lexiredact.metrics`. It does not change ingestion behavior or storage behavior.

Available metrics:

- `MRR`: Mean Reciprocal Rank across queries
- `Recall@K`: average fraction of expected relevant documents found in the top `K`
- `average_first_relevant_rank`: average rank position of the first relevant hit

## API

```python
from lexiredact.metrics import RetrievalMetricsEvaluator
```

Single-query helpers:

```python
RetrievalMetricsEvaluator.reciprocal_rank(expected_ids, retrieved_ids)
RetrievalMetricsEvaluator.recall_at_k(expected_ids, retrieved_ids, k=5)
RetrievalMetricsEvaluator.evaluate_query(
    query_id="q1",
    expected_ids=["doc-1"],
    retrieved_ids=["doc-3", "doc-1", "doc-8"],
    k=5,
)
```

Batch evaluation:

```python
results = RetrievalMetricsEvaluator.evaluate_queries(
    [
        {
            "query_id": "q1",
            "expected_ids": ["doc-1"],
            "retrieved_ids": ["doc-3", "doc-1", "doc-8"],
        },
        {
            "query_id": "q2",
            "expected_ids": ["doc-4", "doc-9"],
            "retrieved_ids": ["doc-4", "doc-7", "doc-9"],
        },
    ],
    k=5,
)
```

Returned shape:

```python
{
    "summary": {
        "total_queries": 2,
        "queries_with_hits": 2,
        "mean_reciprocal_rank": 0.75,
        "recall_at_k": 1.0,
        "average_first_relevant_rank": 1.5,
    },
    "per_query": [...],
}
```

## Recommended Use

Use these metrics when:

- comparing embedding models
- comparing chunking strategies
- comparing vector store settings
- checking whether privacy-safe ingestion still preserves acceptable retrieval quality

Do not treat these metrics as a replacement for task-specific human evaluation. They are a fast screening layer.

## Example

See [`examples/retrieval_metrics_demo.py`](../examples/retrieval_metrics_demo.py) for a minimal reference workflow.
