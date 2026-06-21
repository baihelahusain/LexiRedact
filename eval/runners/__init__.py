"""
eval/runners — Pipeline comparison runners for Lexiredact benchmarking.

  compare.py — run_comparison(): instantiates LexiredactPipeline exactly three times
               (once per pipeline_mode) and runs the same EvalDataset through each.

               Separate ChromaDB collections prevent cross-mode contamination:
                 vs_eval_raw, vs_eval_preredacted, vs_eval_dual

               Warmup: 5 fixed synthetic chunks (not from the dataset) run before
               recording any latency, isolating model-init cost from steady-state.

               Outputs: CompareResult per mode, written as JSON to output_dir for
               offline metric computation by eval/metrics/ and eval/report.py.
"""

from .compare import CompareResult, RetrievalResult, run_comparison

__all__ = [
    "CompareResult",
    "RetrievalResult",
    "run_comparison",
]
