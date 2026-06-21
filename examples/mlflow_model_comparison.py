"""Compare LexiRedact run summaries before logging them to MLflow."""

from __future__ import annotations


def summarize_results(label: str, results) -> dict:
    return {
        "label": label,
        "chunks": len(results),
        "avg_latency_ms": sum(r.latency_ms for r in results) / max(len(results), 1),
        "entities_detected": sum(len(r.entities_detected) for r in results),
        "cache_hits": sum(1 for r in results if r.cache_hit),
    }


def choose_lowest_latency(summaries: list[dict]) -> dict:
    return min(summaries, key=lambda item: item["avg_latency_ms"])


print(
    "Use summarize_results() for runs with different pipeline modes or embedding models, "
    "then log the dictionaries with your experiment tracker."
)
