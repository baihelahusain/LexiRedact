"""
eval/runners/compare.py — Runs all three pipeline modes on the same dataset.

No pipeline code is defined here. Uses LexiredactPipeline as a black box.
Writes raw results to output_dir as JSON for downstream metric computation.

Constraint: separate ChromaDB collection per mode (vs_eval_raw, vs_eval_preredacted,
vs_eval_dual). Results from different modes are NEVER mixed.

Warmup: 5 fixed synthetic chunks (not from the dataset) are run before recording
any latency. This isolates model-init cost from steady-state throughput.

Latency accuracy: After warmup, each dataset chunk is ingested INDIVIDUALLY
(batch size = 1) so that every ProcessingResult.latency_ms reflects a genuine
per-chunk wall-clock measurement rather than a batch-average. This ensures
p50 and p95 percentiles are meaningful and non-identical.

Usage:
  python eval/runners/compare.py \
    --dataset-dir eval/dataset/data/ \
    --output-dir  eval/results/ \
    --config      lexiredact_config.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Allow running as a standalone script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.dataset.schema import EvalDataset, load_dataset
from lexiredact import ProcessingResult, LexiredactPipeline, load_config
from lexiredact.config.schema import LexiredactConfig
from lexiredact.app_logging import configure_logging, get_logger
from lexiredact.pipeline.embedder.default import DefaultEmbedder
from lexiredact.pipeline.store.chroma import ChromaStore

logger = get_logger("eval.compare")

# ── Warmup chunks (fixed, NOT from the eval dataset) ──────────────────────────
_WARMUP_CHUNKS: list[dict[str, str]] = [
    {"id": "_warmup_1", "text": "System initialisation test sentence for model warmup."},
    {"id": "_warmup_2", "text": "Another warmup chunk to ensure embedder is fully loaded."},
    {"id": "_warmup_3", "text": "Warmup text three — used to pre-heat the inference pipeline."},
    {"id": "_warmup_4", "text": "Fourth warmup document for stable latency baseline."},
    {"id": "_warmup_5", "text": "Final warmup chunk before steady-state benchmarking begins."},
]


# ── Result dataclasses ─────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """Retrieval outcome for a single query."""
    query_id: str
    query_text: str
    retrieved_chunk_ids: list[str]   # ordered by similarity, length = top_k
    relevant_chunk_ids: list[str]    # ground truth from EvalQuery
    distances: list[float]           # cosine distance scores from store.query()


@dataclass
class CompareResult:
    """All results for one pipeline mode run."""
    mode: str
    ingest_results: list[ProcessingResult]     # one per dataset chunk (post-warmup)
    retrieval_results: list[RetrievalResult]   # one per query
    warmup_latency_ms: float                   # avg latency of 5 warmup chunks
    warmup_chunk_count: int                    # always 5


# ── Core comparison runner ────────────────────────────────────────────────────

def run_comparison(
    dataset: EvalDataset,
    base_config: LexiredactConfig,
    output_dir: str,
    top_k: int = 5,
) -> dict[str, CompareResult]:
    """Run all three pipeline modes and collect results.

    For each mode:
      1. Clone config, override pipeline_mode + collection_name (prevents cross-contamination).
      2. Run 5 warmup chunks (NOT from dataset) to initialise models.
      3. Ingest each dataset chunk INDIVIDUALLY (batch size = 1) for accurate per-chunk latency.
      4. Query the store for every EvalQuery using query_embed().
      5. Record RetrievalResult per query.

    Latency note: individual ingestion (one chunk at a time) is critical for honest
    p50/p95 percentile computation. Batch ingestion would produce identical latency_ms
    for every chunk (batch_total / n), making percentiles meaningless.

    Args:
        dataset:     Annotated eval dataset (chunks + queries).
        base_config: Base LexiredactConfig — pipeline_mode and collection will be overridden.
        output_dir:  Directory where JSON results are written per mode.
        top_k:       Number of results to retrieve per query.

    Returns:
        Dict mapping mode name → CompareResult.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    modes = ["raw", "preredacted", "dual"]
    all_results: dict[str, CompareResult] = {}

    # Pre-build raw dicts from EvalChunk (reused across all 3 modes).
    raw_chunk_dicts = [
        {"id": chunk.chunk_id, "text": chunk.raw_text}
        for chunk in dataset.chunks
    ]

    for mode in modes:
        logger.info("=== Running mode: %s ===", mode)

        # 1. Clone config with mode-specific overrides.
        mode_config = base_config.model_copy(update={
            "pipeline_mode": mode,
            "store": base_config.store.model_copy(update={
                "collection_name": f"vs_eval_{mode}",
            }),
        })

        pipeline = LexiredactPipeline(mode_config)

        # 2. Warmup — 5 fixed chunks, results NOT included in metrics.
        logger.info("Warming up with %d fixed chunks...", len(_WARMUP_CHUNKS))
        warmup_results = pipeline.ingest(_WARMUP_CHUNKS)
        warmup_latency_ms = (
            sum(r.latency_ms for r in warmup_results) / len(warmup_results)
            if warmup_results else 0.0
        )
        logger.info("Warmup avg latency: %.1f ms", warmup_latency_ms)

        # 3. Ingest each dataset chunk INDIVIDUALLY for accurate per-chunk latency.
        # This ensures latency_ms in each ProcessingResult reflects true single-chunk
        # end-to-end time (PII detect + embed + store) rather than a batch average.
        ingest_results: list[ProcessingResult] = []
        total_chunks = len(raw_chunk_dicts)
        logger.info(
            "Ingesting %d dataset chunks individually for accurate per-chunk latency...",
            total_chunks,
        )
        for i, chunk_dict in enumerate(raw_chunk_dicts):
            if (i + 1) % 50 == 0 or i == total_chunks - 1:
                logger.info("  Progress: %d/%d chunks ingested", i + 1, total_chunks)
            single_result = pipeline.ingest([chunk_dict])
            if single_result:
                ingest_results.extend(single_result)

        avg_steady = (
            sum(r.latency_ms for r in ingest_results) / len(ingest_results)
            if ingest_results else 0.0
        )
        logger.info("Steady-state avg latency: %.1f ms", avg_steady)

        # 4. Build embedder + store for query-time retrieval.
        embedder = DefaultEmbedder(mode_config.embedder)
        store = ChromaStore(mode_config.store, embedder.get_dimension())

        # 5. Query the store for every EvalQuery.
        retrieval_results: list[RetrievalResult] = []
        logger.info("Running %d retrieval queries...", len(dataset.queries))

        for query in dataset.queries:
            # Use query_embed() which applies "query: " prefix (not "passage: ").
            query_vectors = embedder.query_embed([query.query_text])
            query_vector = query_vectors[0]

            hits = store.query(query_vector, top_k=top_k)
            retrieval_results.append(RetrievalResult(
                query_id=query.query_id,
                query_text=query.query_text,
                retrieved_chunk_ids=[h["id"] for h in hits],
                relevant_chunk_ids=query.relevant_chunk_ids,
                distances=[h["distance"] for h in hits],
            ))

        compare_result = CompareResult(
            mode=mode,
            ingest_results=ingest_results,
            retrieval_results=retrieval_results,
            warmup_latency_ms=warmup_latency_ms,
            warmup_chunk_count=len(_WARMUP_CHUNKS),
        )
        all_results[mode] = compare_result

        # 6. Persist to JSON for offline metric computation.
        _save_compare_result(compare_result, output_dir)
        logger.info("Mode '%s' complete. Results saved to %s/", mode, output_dir)

    return all_results


# ── JSON persistence ──────────────────────────────────────────────────────────

def _save_compare_result(result: CompareResult, output_dir: str) -> None:
    """Serialise CompareResult to JSON in output_dir/{mode}_results.json.

    Includes the full per-chunk latency list as ``latency_ms_list`` so that
    statistical metrics (std dev, percentiles) can be recomputed offline without
    re-running the pipeline. Also includes ``stage_latencies`` per chunk.
    """
    payload = {
        "mode": result.mode,
        "warmup_latency_ms": result.warmup_latency_ms,
        "warmup_chunk_count": result.warmup_chunk_count,
        # Convenience field for quick offline recomputation of percentiles / std dev.
        "latency_ms_list": [round(r.latency_ms, 2) for r in result.ingest_results],
        "ingest_results": [r.to_dict() for r in result.ingest_results],
        "retrieval_results": [
            {
                "query_id": r.query_id,
                "query_text": r.query_text,
                "retrieved_chunk_ids": r.retrieved_chunk_ids,
                "relevant_chunk_ids": r.relevant_chunk_ids,
                "distances": r.distances,
            }
            for r in result.retrieval_results
        ],
    }
    out_path = Path(output_dir) / f"{result.mode}_results.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved %s", out_path)


def load_compare_result(results_dir: str, mode: str) -> CompareResult:
    """Load a previously saved CompareResult from JSON.

    Used by report.py to regenerate graphs without re-running the pipeline.
    Deserializes stage_latencies from each ingest result if present.
    """
    from lexiredact.models.result import DetectedEntity, ProcessingResult

    path = Path(results_dir) / f"{mode}_results.json"
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    ingest_results: list[ProcessingResult] = []
    for r in data["ingest_results"]:
        entities = [
            DetectedEntity(
                text=e["text"],
                entity_type=e["entity_type"],
                start=e["start"],
                end=e["end"],
                score=e["score"],
            )
            for e in r.get("entities_detected", [])
        ]
        ingest_results.append(ProcessingResult(
            chunk_id=r["chunk_id"],
            sanitized_text=r["sanitized_text"],
            entities_detected=entities,
            embedding_stored=r["embedding_stored"],
            latency_ms=r["latency_ms"],
            cache_hit=r["cache_hit"],
            pipeline_mode=r["pipeline_mode"],
            error=r.get("error"),
            stage_latencies=r.get("stage_latencies"),  # None for older result files
        ))

    retrieval_results: list[RetrievalResult] = []
    for r in data["retrieval_results"]:
        retrieval_results.append(RetrievalResult(
            query_id=r["query_id"],
            query_text=r["query_text"],
            retrieved_chunk_ids=r["retrieved_chunk_ids"],
            relevant_chunk_ids=r["relevant_chunk_ids"],
            distances=r["distances"],
        ))

    return CompareResult(
        mode=data["mode"],
        ingest_results=ingest_results,
        retrieval_results=retrieval_results,
        warmup_latency_ms=data["warmup_latency_ms"],
        warmup_chunk_count=data["warmup_chunk_count"],
    )


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_logging("INFO")

    parser = argparse.ArgumentParser(
        description="Run all 3 LexiRedact pipeline modes on an eval dataset."
    )
    parser.add_argument("--dataset-dir", required=True,
                        help="Dir containing chunks.json and queries.json")
    parser.add_argument("--output-dir", required=True,
                        help="Dir to write {mode}_results.json files")
    parser.add_argument("--config", required=True,
                        help="Path to lexiredact_config.yaml")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Number of results per query (default: 5)")
    args = parser.parse_args()

    dataset = load_dataset(
        chunks_path=os.path.join(args.dataset_dir, "chunks.json"),
        queries_path=os.path.join(args.dataset_dir, "queries.json"),
    )
    print(f"Loaded dataset: {len(dataset.chunks)} chunks, {len(dataset.queries)} queries")

    base_config = load_config(args.config)
    results = run_comparison(dataset, base_config, args.output_dir, top_k=args.top_k)

    print("\nComparison complete:")
    for mode, cr in results.items():
        n = len(cr.ingest_results)
        avg_lat = sum(r.latency_ms for r in cr.ingest_results) / max(n, 1)
        print(f"  {mode:>12s}: {n} chunks | steady avg {avg_lat:.1f}ms "
              f"| warmup {cr.warmup_latency_ms:.1f}ms")