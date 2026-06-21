"""
eval/metrics — Metric computation modules for Lexiredact evaluation.

  privacy.py — compute_privacy_metrics(): PII recall and FNR broken down by entity type.
               Compares Presidio output (ProcessingResult.entities_detected) against
               ground-truth annotations (EvalChunk.annotated_entities).

  utility.py — compute_utility_metrics(): Hit@K (K=1, 3, 5) and Mean Reciprocal Rank.
               Measures retrieval quality using ground-truth relevant_chunk_ids from EvalQuery.

  latency.py — compute_latency_metrics(): warmup vs steady-state latency, p50/p95
               percentiles, throughput (chunks/sec), and Redis cache hit rate.
               Warmup and steady-state are ALWAYS reported separately.
"""

from eval.metrics.latency import LatencyMetrics, compute_latency_metrics
from eval.metrics.privacy import PrivacyMetrics, compute_privacy_metrics
from eval.metrics.utility import UtilityMetrics, compute_utility_metrics

__all__ = [
    "LatencyMetrics",
    "compute_latency_metrics",
    "PrivacyMetrics",
    "compute_privacy_metrics",
    "UtilityMetrics",
    "compute_utility_metrics",
]
