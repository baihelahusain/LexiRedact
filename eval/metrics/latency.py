"""
eval/metrics/latency.py — Per-chunk ingestion latency and throughput metrics.

Warmup and steady-state are ALWAYS reported separately. They must never be
averaged together — warmup includes one-time model initialisation cost that
is irrelevant to production throughput.

p50 / p95 are computed from the per-chunk latency distribution using
statistics.quantiles() with interpolation method="inclusive" to match
standard percentile definitions. When n < 20, falls back to direct sorted
indexing to avoid ValueError from quantiles().

throughput_chunks_per_sec = 1000 / steady_latency_ms
  (converts milliseconds-per-chunk → chunks-per-second)

avg_stage_latencies: dict of stage_name → mean ms across all chunks.
  Keys vary by mode:
    dual        — {"pii_ms", "embed_redact_ms", "store_ms"}
    preredacted — {"pii_ms", "redact_ms", "embed_ms", "store_ms"}
    raw         — {"embed_ms", "store_ms"}
  Empty dict if no stage_latencies were recorded (older result files).
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.runners.compare import CompareResult


@dataclass
class LatencyMetrics:
    """Per-chunk latency and throughput statistics for one pipeline mode.

    Attributes:
        mode:                   Pipeline mode label.
        warmup_latency_ms:      Average per-chunk latency during the 5-chunk warmup.
                                Includes model initialisation cost.
        steady_latency_ms:      Average per-chunk latency for the full dataset
                                (post-warmup). Reflects production throughput.
        std_dev_ms:             Standard deviation of per-chunk latency.
                                Zero when only one chunk measured.
        min_latency_ms:         Minimum per-chunk latency observed.
        max_latency_ms:         Maximum per-chunk latency observed.
        p50_latency_ms:         Median latency across post-warmup chunks.
        p95_latency_ms:         95th percentile latency (tail latency indicator).
        throughput_chunks_per_sec: Chunks processed per second at steady state.
                                   Derived as ``1000 / steady_latency_ms``.
        cache_hit_rate:         Fraction of chunks whose embedding was served
                                from Redis cache (0.0 when cache disabled).
        avg_stage_latencies:    Per-stage mean latencies in ms, averaged across
                                all chunks. Keys vary by pipeline mode.
                                Empty dict if stage timing was not recorded.
    """

    mode: str
    warmup_latency_ms: float
    steady_latency_ms: float
    std_dev_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    throughput_chunks_per_sec: float
    cache_hit_rate: float
    avg_stage_latencies: dict[str, float] = field(default_factory=dict)


def compute_latency_metrics(compare_result: CompareResult) -> LatencyMetrics:
    """Compute latency and throughput metrics from a CompareResult.

    Uses ``compare_result.ingest_results`` for per-chunk latency values
    and ``compare_result.warmup_latency_ms`` for the warmup figure.

    Percentile computation:
      - n >= 20: uses ``statistics.quantiles(n=20, method="inclusive")`` for
        accurate interpolation matching standard percentile definitions.
      - n < 20: falls back to sorted-list indexing to avoid ValueError.

    Args:
        compare_result: Full results for one pipeline mode.

    Returns:
        A :class:`LatencyMetrics` instance with warmup and steady-state
        figures always populated separately.
    """
    results = compare_result.ingest_results
    warmup_ms = compare_result.warmup_latency_ms

    if not results:
        return LatencyMetrics(
            mode=compare_result.mode,
            warmup_latency_ms=warmup_ms,
            steady_latency_ms=0.0,
            std_dev_ms=0.0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            throughput_chunks_per_sec=0.0,
            cache_hit_rate=0.0,
            avg_stage_latencies={},
        )

    latencies: list[float] = [r.latency_ms for r in results]
    n = len(latencies)

    steady_ms = statistics.mean(latencies)
    std_dev_ms = statistics.stdev(latencies) if n >= 2 else 0.0
    min_ms = min(latencies)
    max_ms = max(latencies)

    # Percentile computation — safe for any n >= 1
    if n >= 20:
        quantiles_20 = statistics.quantiles(latencies, n=20, method="inclusive")
        p50_ms = quantiles_20[9]   # 10th of 20 = 50th percentile
        p95_ms = quantiles_20[18]  # 19th of 20 = 95th percentile
    elif n >= 2:
        sorted_lats = sorted(latencies)
        p50_idx = max(0, int(n * 0.50) - 1)
        p95_idx = max(0, min(int(n * 0.95), n - 1))
        p50_ms = sorted_lats[p50_idx]
        p95_ms = sorted_lats[p95_idx]
    else:
        p50_ms = p95_ms = latencies[0]

    throughput = 1000.0 / steady_ms if steady_ms > 0 else 0.0
    cache_hits = sum(1 for r in results if r.cache_hit)
    cache_hit_rate = cache_hits / n

    # Aggregate per-stage latencies across all chunks.
    stage_sums: dict[str, float] = defaultdict(float)
    stage_counts: dict[str, int] = defaultdict(int)
    for r in results:
        if r.stage_latencies:
            for stage_key, stage_val in r.stage_latencies.items():
                stage_sums[stage_key] += stage_val
                stage_counts[stage_key] += 1

    avg_stage_latencies: dict[str, float] = {
        k: round(stage_sums[k] / stage_counts[k], 2)
        for k in stage_sums
        if stage_counts[k] > 0
    }

    return LatencyMetrics(
        mode=compare_result.mode,
        warmup_latency_ms=round(warmup_ms, 2),
        steady_latency_ms=round(steady_ms, 2),
        std_dev_ms=round(std_dev_ms, 2),
        min_latency_ms=round(min_ms, 2),
        max_latency_ms=round(max_ms, 2),
        p50_latency_ms=round(p50_ms, 2),
        p95_latency_ms=round(p95_ms, 2),
        throughput_chunks_per_sec=round(throughput, 2),
        cache_hit_rate=round(cache_hit_rate, 4),
        avg_stage_latencies=avg_stage_latencies,
    )