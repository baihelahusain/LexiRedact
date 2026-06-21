"""
demo — Streamlit demo application for Lexiredact (repository-only, not part of PyPI package).

Run from the repository root::

    streamlit run demo/app.py

The demo provides four tabs:
  1. Live Demo          — single-chunk pipeline run with real-time PII highlighting.
  2. 3-Mode Comparison  — same 5 chunks through raw / preredacted / dual side-by-side.
  3. Benchmark Results  — 4 pre-generated PNG graphs (requires running eval/report.py first).
  4. Query Explorer     — semantic search over the dual-mode ChromaDB collection.
"""
