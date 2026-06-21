"""
eval — Evaluation suite for lexiredact.

Not part of the PyPI package. Run scripts directly from the repo root:

  python eval/dataset/sample_generator.py --output-dir eval/dataset/data/
  python eval/runners/compare.py --dataset-dir eval/dataset/data/ \
         --output-dir eval/results/ --config lexiredact_config.yaml
  python eval/report.py --results-dir eval/results/ --output-dir eval/results/graphs/

Sub-packages:
  dataset/   — EvalDataset schema and synthetic data generator
  runners/   — compare.py runs all 3 pipeline modes, writes JSON results
  metrics/   — privacy, utility, and latency metric computations
  report.py  — generates 4 benchmark PNG graphs from metric objects
"""