"""
demo/app.py — LexiRedact Professional Dashboard
================================================
Multi-page Streamlit application providing:
  1. Dashboard      — Collection health, ingestion stats, system status
  2. Ingest         — Upload JSON dataset, map schema fields, run pipeline
  3. PII Inspector  — Single/batch chunk analysis with live PII highlighting
  4. Query Lab      — Semantic search with distance thresholds, relevance filtering
  5. Comparator     — Side-by-side 3-mode pipeline comparison with inline metrics
  6. Analytics      — PII entity distribution, latency profiles, privacy metrics

Usage:
  streamlit run demo/app.py

Changes vs original:
  - page_comparator(): stage latency breakdown per mode; inline retrieval quality
    evaluation (Hit@5, Recall@5, nDCG@5, MRR) with optional query + relevant IDs.
  - page_analytics(): fixed p95 formula (statistics.quantiles n=20 inclusive);
    mean ± std displayed on latency metric; stage latency breakdown per mode;
    retrieval metrics (Hit@5, Recall@5, nDCG@5, MRR) shown when eval JSON with
    retrieval_results is loaded via Upload; cross-mode table uses corrected p95.
  - _config_panel(): backend selector, model text_input, document/query prefix
    inputs, NLP engine selector replaces fixed spaCy selectbox.
  - _build_config(): accepts new backend/prefix/nlp_engine/nlp_model parameters.
  - page_query_lab() and page_comparator(): use create_embedder() registry instead
    of DefaultEmbedder directly.

NOTE on stage_latencies and Streamlit compatibility:
  ProcessingResult.stage_latencies is Optional[dict] defaulting to None.
  Existing pipeline.ingest() calls still return ProcessingResult as before —
  no API change. The new orchestrator populates stage_latencies automatically.
  All Streamlit pages handle None gracefully (shown as "—" or hidden).
"""

from __future__ import annotations

import io
import json
import math
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

# ── Repo root on sys.path ─────────────────────────────────────────────────────
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── LexiRedact imports ──────────────────────────────────────────────────────
try:
    from lexiredact import LexiredactPipeline
    from lexiredact.config.schema import (
        CacheConfig, EmbedderConfig, InputSchemaConfig,
        PIIConfig, StoreConfig, LexiredactConfig,
    )
    from lexiredact.pipeline.embedder.registry import create_embedder
    from lexiredact.pipeline.store.chroma import ChromaStore
    VS_AVAILABLE = True
except ImportError as _e:
    VS_AVAILABLE = False
    _VS_IMPORT_ERROR = str(_e)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & THEME
# ═══════════════════════════════════════════════════════════════════════════════

ALL_PII_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION",
    "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS", "DATE_TIME",
    "NRP", "MEDICAL_LICENSE", "URL",
]

PIPELINE_MODES = {
    "dual": "Dual Pipeline — embed original, store sanitized (recommended)",
    "preredacted": "Pre-Redacted — detect → redact → embed sanitized (sequential)",
    "raw": "Raw — embed & store original text, no PII step (baseline only)",
}

SPACY_MODELS = ["en_core_web_sm", "en_core_web_md", "en_core_web_lg", "en_core_web_trf"]

MODE_COLORS = {"raw": "#E57373", "preredacted": "#64B5F6", "dual": "#81C784"}
MODE_ICONS  = {"raw": "⚪", "preredacted": "🔵", "dual": "🟢"}

# Cosine distance: 0.0 = identical, higher = less similar
DISTANCE_EXCELLENT = 0.30
DISTANCE_GOOD      = 0.50
DISTANCE_MARGINAL  = 0.70

SAMPLE_DATASET = [
    {"id": "sample_001", "text": "John Smith contacted billing at john.smith@acme.com regarding invoice #7821. His Visa card 4111-1111-1111-1111 was charged $349.00 in error.", "department": "billing"},
    {"id": "sample_002", "text": "Employee Maria Garcia, based in Austin TX, called +1-555-0182 about a payroll discrepancy. Senior Engineer in Finance, hired 2023-03-15.", "department": "hr"},
    {"id": "sample_003", "text": "Patient David Lee admitted 2024-11-02 at Houston General for chronic fatigue syndrome. Emergency contact: +1-713-555-9034.", "department": "medical"},
    {"id": "sample_004", "text": "Security alert: devops@company.io triggered brute-force login from IP 192.168.45.12 on 2024-10-30. Phone verification sent to +1-650-555-0093.", "department": "it_security"},
    {"id": "sample_005", "text": "Case #CV-448812 — plaintiff Robert Chen (rchen@lawmail.com) vs Apex Legal LLP. Hearing in Chicago on 2025-01-15. Counsel at +1-312-555-7700.", "department": "legal"},
    {"id": "sample_006", "text": "Kimberly Adams submitted billing dispute for invoice #7224 on 2026-03-08. Email: cartereric@example.org. Card 4039117182278241 charged incorrectly.", "department": "billing"},
    {"id": "sample_007", "text": "Ashley Hall joined Engineering on 2026-01-05. Located in Watsonside. Phone: 446.812.0047x113. Transferred as Director.", "department": "hr"},
    {"id": "sample_008", "text": "Admin rebeccaarnold@example.net reset password after credential stuffing. Phone verification: +1-972-356-3942. IP logged: 138.157.46.67.", "department": "it_security"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="LexiRedact Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "LexiRedact — Privacy-preserving RAG ingestion middleware"},
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Typography */
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  code, .stCode, pre { font-family: 'IBM Plex Mono', monospace !important; }

  /* Sidebar */
  [data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
  [data-testid="stSidebar"] * { color: #c9d1d9 !important; }
  [data-testid="stSidebar"] .stRadio label { padding: 6px 12px; border-radius: 6px; cursor:pointer; transition: background 0.15s; }
  [data-testid="stSidebar"] .stRadio label:hover { background: #161b22; }

  /* Metric cards */
  [data-testid="metric-container"] { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 14px !important; }

  /* Relevance badges */
  .badge-excellent { background:#0d4429; color:#3fb950; padding:2px 8px; border-radius:4px; font-size:11px; font-family:'IBM Plex Mono',monospace; font-weight:600; }
  .badge-good      { background:#0c2d6b; color:#58a6ff; padding:2px 8px; border-radius:4px; font-size:11px; font-family:'IBM Plex Mono',monospace; font-weight:600; }
  .badge-marginal  { background:#3d2f00; color:#e3b341; padding:2px 8px; border-radius:4px; font-size:11px; font-family:'IBM Plex Mono',monospace; font-weight:600; }
  .badge-poor      { background:#3d1212; color:#f85149; padding:2px 8px; border-radius:4px; font-size:11px; font-family:'IBM Plex Mono',monospace; font-weight:600; }

  /* PII highlight */
  .pii-span { background:#3d1212; border:1px solid #f85149; color:#f85149; border-radius:3px; padding:1px 4px; font-weight:600; font-size:0.92em; }
  .redacted-span { background:#0d3a2a; border:1px solid #3fb950; color:#3fb950; border-radius:3px; padding:1px 5px; font-weight:600; font-size:0.88em; font-family:'IBM Plex Mono',monospace; }

  /* Result cards */
  .result-card { background:#161b22; border:1px solid #21262d; border-radius:10px; padding:16px; margin-bottom:12px; }
  .result-card:hover { border-color:#30363d; }

  /* Status chip */
  .chip-ok   { display:inline-block; background:#0d4429; color:#3fb950; padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600; }
  .chip-warn { display:inline-block; background:#3d2f00; color:#e3b341; padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600; }
  .chip-err  { display:inline-block; background:#3d1212; color:#f85149; padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600; }

  /* Section headers */
  .section-title { font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:#8b949e; margin-bottom:8px; }

  /* Stage bar segment */
  .stage-bar { display:inline-block; height:20px; border-radius:3px; margin-right:2px; vertical-align:middle; }

  /* Progress table */
  .stDataFrame { border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════

def _init_state() -> None:
    defaults = {
        "page": "Dashboard",
        # Ingestion
        "ingest_results": [],
        "ingest_collection": None,
        "ingest_config": None,
        "ingest_dataset": None,
        # Inspector
        "inspector_results": [],
        # Query
        "query_hits": [],
        "query_collection": None,
        # Comparator
        "compare_results": {},
        "compare_dataset": None,
        "compare_retrieval_metrics": {},   # mode → {hit5, recall5, ndcg5, mrr} from inline eval
        # Analytics
        "analytics_results": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — General
# ═══════════════════════════════════════════════════════════════════════════════

def _vs_guard() -> bool:
    if not VS_AVAILABLE:
        st.error(f"**LexiRedact not importable.** Install dependencies first.\n\n`{_VS_IMPORT_ERROR}`")
        return False
    return True


def _build_config(
    mode: str,
    collection: str,
    entities: list[str],
    spacy_model: str,
    nlp_engine: str,
    nlp_model: str,
    score_threshold: float,
    batch_size: int,
    embed_backend: str,
    embed_model: str,
    doc_prefix: str,
    query_prefix: str,
    embed_batch: int,
    device: str,
    normalize: bool,
    cache_enabled: bool,
    redis_url: str,
    ttl: int,
    persist_dir: str,
    id_field: str = "id",
    text_field: str = "text",
    metadata_fields: list[str] | None = None,
) -> LexiredactConfig:
    return LexiredactConfig(
        pipeline_mode=mode,
        input_schema=InputSchemaConfig(
            id_field=id_field,
            text_field=text_field,
            metadata_fields=metadata_fields or [],
        ),
        pii=PIIConfig(
            entities=entities,
            nlp_engine=nlp_engine,
            nlp_model=nlp_model,
            spacy_model=spacy_model,
            score_threshold=score_threshold,
            batch_size=batch_size,
        ),
        embedder=EmbedderConfig(
            backend=embed_backend,
            model_name=embed_model,
            document_prefix=doc_prefix,
            query_prefix=query_prefix,
            batch_size=embed_batch,
            device=device,
            normalize_embeddings=normalize,
        ),
        cache=CacheConfig(enabled=cache_enabled, redis_url=redis_url, ttl_seconds=ttl),
        store=StoreConfig(
            collection_name=collection,
            persist_directory=persist_dir,
        ),
    )


def _distance_badge(d: float) -> str:
    if d < DISTANCE_EXCELLENT:
        return f'<span class="badge-excellent">⬆ EXCELLENT · {d:.3f}</span>'
    if d < DISTANCE_GOOD:
        return f'<span class="badge-good">✓ GOOD · {d:.3f}</span>'
    if d < DISTANCE_MARGINAL:
        return f'<span class="badge-marginal">~ MARGINAL · {d:.3f}</span>'
    return f'<span class="badge-poor">✗ POOR · {d:.3f}</span>'


def _distance_color(d: float) -> str:
    if d < DISTANCE_EXCELLENT: return "#3fb950"
    if d < DISTANCE_GOOD:      return "#58a6ff"
    if d < DISTANCE_MARGINAL:  return "#e3b341"
    return "#f85149"


def _highlight_pii(text: str, entities: list) -> str:
    if not entities:
        return text.replace("<", "&lt;").replace(">", "&gt;")
    chars = list(text)
    for ent in sorted(entities, key=lambda e: e.start, reverse=True):
        span = text[ent.start:ent.end]
        replacement = list(f'<span class="pii-span" title="{ent.entity_type} · score {ent.score:.2f}">{span}</span>')
        chars[ent.start:ent.end] = replacement
    return "".join(chars)


def _highlight_redacted(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(
        r"&lt;(\w+)&gt;",
        r'<span class="redacted-span">&lt;\1&gt;</span>',
        escaped,
    )


def _parse_uploaded_json(uploaded_file) -> list[dict] | None:
    try:
        content = uploaded_file.read()
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and any(isinstance(v, list) for v in data.values()):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v
        st.error("JSON must be a top-level array of objects `[{...}, ...]`")
        return None
    except json.JSONDecodeError as e:
        st.error(f"JSON parse error: {e}")
        return None


def _detect_fields(records: list[dict]) -> list[str]:
    all_keys: set[str] = set()
    for r in records[:50]:
        all_keys.update(r.keys())
    return sorted(all_keys)


def _sanitize_metadata_for_chroma(meta: dict) -> tuple[dict, list[str]]:
    clean: dict = {}
    skipped: list[str] = []
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            try:
                clean[k] = json.dumps(v, ensure_ascii=False)
            except (TypeError, ValueError):
                try:
                    clean[k] = str(v)
                except Exception:
                    skipped.append(k)
    return clean, skipped


def _analyze_query_relevance(
    hits: list[dict],
    dist_threshold: float,
    spread_threshold: float,
) -> dict:
    if not hits:
        return {
            "relevant": [], "filtered_out": [], "is_discriminative": True,
            "warn_low_spread": False, "diagnostics": {},
        }

    distances = [h["distance"] for h in hits]
    min_d = min(distances)
    max_d = max(distances)
    spread = max_d - min_d
    std_dev = statistics.stdev(distances) if len(distances) >= 2 else 0.0
    mean_d = statistics.mean(distances)

    relevant = [h for h in hits if h["distance"] <= dist_threshold]
    filtered_out = [h for h in hits if h["distance"] > dist_threshold]
    is_discriminative = spread >= spread_threshold
    warn_low_spread = not is_discriminative

    return {
        "relevant": relevant,
        "filtered_out": filtered_out,
        "is_discriminative": is_discriminative,
        "warn_low_spread": warn_low_spread,
        "diagnostics": {
            "min_dist": min_d, "max_dist": max_d, "spread": spread,
            "std_dev": std_dev, "mean_dist": mean_d, "n_total": len(hits),
        },
    }


def _get_collections(persist_dir: str = "./chroma_db") -> list[str]:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=persist_dir)
        return [c.name for c in client.list_collections()]
    except Exception:
        return []


def _collection_count(collection_name: str, persist_dir: str = "./chroma_db") -> int:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=persist_dir)
        col = client.get_collection(collection_name)
        return col.count()
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — Retrieval metrics (self-contained, no eval module import required)
# ═══════════════════════════════════════════════════════════════════════════════

def _hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(c in relevant for c in retrieved[:k]) else 0.0


def _recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for c in retrieved[:k] if c in relevant) / len(relevant)


def _ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, c in enumerate(retrieved[:k], start=1)
        if c in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def _mrr_single(retrieved: list[str], relevant: set[str]) -> float:
    for i, c in enumerate(retrieved, start=1):
        if c in relevant:
            return 1.0 / i
    return 0.0


def _compute_retrieval_metrics(
    queries_results: list[tuple[list[str], set[str]]],
    k: int = 5,
) -> dict[str, float]:
    if not queries_results:
        return {"hit_at_k": 0.0, "recall_at_k": 0.0, "ndcg_at_k": 0.0, "mrr": 0.0}

    n = len(queries_results)
    hit_sum = recall_sum = ndcg_sum = mrr_sum = 0.0

    for retrieved, relevant in queries_results:
        hit_sum    += _hit_at_k(retrieved, relevant, k)
        recall_sum += _recall_at_k(retrieved, relevant, k)
        ndcg_sum   += _ndcg_at_k(retrieved, relevant, k)
        mrr_sum    += _mrr_single(retrieved, relevant)

    return {
        "hit_at_k":    round(hit_sum / n, 4),
        "recall_at_k": round(recall_sum / n, 4),
        "ndcg_at_k":   round(ndcg_sum / n, 4),
        "mrr":         round(mrr_sum / n, 4),
    }


def _p95_latency(lats: list[float]) -> float:
    n = len(lats)
    if n == 0:
        return 0.0
    if n >= 20:
        return statistics.quantiles(lats, n=20, method="inclusive")[18]
    if n >= 2:
        return sorted(lats)[min(int(n * 0.95), n - 1)]
    return lats[0]


def _render_stage_breakdown_html(stage_lat: dict[str, float], mode: str) -> str:
    if not stage_lat:
        return "<em style='color:#8b949e;font-size:12px;'>No stage data recorded</em>"

    stage_colors: dict[str, str] = {
        "pii_ms":          "#7986CB",
        "embed_redact_ms": "#4DB6AC",
        "redact_ms":       "#FFB74D",
        "embed_ms":        "#4DB6AC",
        "store_ms":        "#F06292",
    }
    stage_labels: dict[str, str] = {
        "pii_ms":          "PII",
        "embed_redact_ms": "Embed+Redact(∥)",
        "redact_ms":       "Redact",
        "embed_ms":        "Embed",
        "store_ms":        "Store",
    }
    total = sum(stage_lat.values()) or 1.0
    segments = []
    for key, val in stage_lat.items():
        if val <= 0:
            continue
        pct = val / total * 100
        color = stage_colors.get(key, "#9E9E9E")
        label = stage_labels.get(key, key)
        segments.append(
            f'<span title="{label}: {val:.1f}ms ({pct:.0f}%)" '
            f'style="display:inline-block;width:{pct:.1f}%;min-width:4px;'
            f'height:16px;background:{color};border-radius:2px;margin-right:1px;'
            f'vertical-align:middle;"></span>'
        )
    bar_html = "".join(segments)
    detail = " | ".join(
        f'<span style="color:{stage_colors.get(k,"#9E9E9E")};font-weight:600;">'
        f'{stage_labels.get(k,k)}</span>: {v:.1f}ms'
        for k, v in stage_lat.items() if v > 0
    )
    return (
        f'<div style="width:100%;background:#0d1117;border-radius:4px;padding:2px 0;">'
        f'{bar_html}'
        f'</div>'
        f'<div style="font-size:11px;margin-top:4px;font-family:IBM Plex Mono,monospace;'
        f'color:#8b949e;">{detail}</div>'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

def _sidebar() -> str:
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 8px 0;">
          <div style="font-size:22px;font-weight:700;letter-spacing:-0.5px;color:#f0f6fc;">
            🛡️ LexiRedact
          </div>
          <div style="font-size:11px;color:#8b949e;margin-top:2px;font-family:'IBM Plex Mono',monospace;">
            v0.0.2 · Privacy-Preserving RAG
          </div>
        </div>
        <hr style="border-color:#21262d;margin:8px 0 16px 0;">
        """, unsafe_allow_html=True)

        pages = [
            "🏠  Dashboard",
            "📥  Ingest",
            "🔬  PII Inspector",
            "🔍  Query Lab",
            "⚖️  Comparator",
            "📊  Analytics",
        ]
        selected = st.radio("Navigation", pages, label_visibility="collapsed")
        page = selected.split("  ", 1)[1].strip()

        st.markdown("<hr style='border-color:#21262d;margin:16px 0;'>", unsafe_allow_html=True)

        st.markdown('<div class="section-title">System Status</div>', unsafe_allow_html=True)
        if VS_AVAILABLE:
            st.markdown('<span class="chip-ok">● LexiRedact OK</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="chip-err">● Import Error</span>', unsafe_allow_html=True)

        collections = _get_collections()
        if collections:
            st.markdown(f'<span class="chip-ok">● {len(collections)} Collection(s)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="chip-warn">● No Collections</span>', unsafe_allow_html=True)

        if st.session_state.ingest_results:
            n = len(st.session_state.ingest_results)
            st.markdown(f'<span class="chip-ok">● {n} Chunks Ingested</span>', unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#21262d;margin:12px 0;'>", unsafe_allow_html=True)
        st.caption("Dual pipeline: embeddings from original text; only sanitized text stored in vector DB.")

    return page

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard() -> None:
    st.title("🏠 Dashboard")
    st.caption("Collection health, ingestion history, and system overview.")
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        status = "✅ Ready" if VS_AVAILABLE else "❌ Error"
        st.metric("lexiredact", status)
    with c2:
        collections = _get_collections()
        st.metric("Collections", len(collections))
    with c3:
        total_chunks = sum(_collection_count(c) for c in collections)
        st.metric("Total Vectors", f"{total_chunks:,}")
    with c4:
        results = st.session_state.ingest_results
        if results:
            avg_lat = sum(r.latency_ms for r in results) / len(results)
            st.metric("Last Ingest Avg Latency", f"{avg_lat:.1f} ms")
        else:
            st.metric("Last Ingest Avg Latency", "—")

    st.divider()

    st.markdown("### Vector Store Collections")
    if collections:
        col_data = []
        for name in collections:
            count = _collection_count(name)
            col_data.append({"Collection": name, "Vectors": count, "Status": "Active" if count > 0 else "Empty"})
        st.dataframe(col_data, use_container_width=True, hide_index=True)
    else:
        st.info("No collections found. Use **📥 Ingest** to create one.", icon="ℹ️")

    if st.session_state.ingest_results:
        st.markdown("### Last Ingestion Summary")
        results = st.session_state.ingest_results
        cfg = st.session_state.ingest_config

        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Chunks Processed", len(results))
        r2.metric("Pipeline Mode", cfg.pipeline_mode if cfg else "—")
        r3.metric("Cache Hits", sum(1 for r in results if r.cache_hit))
        pii_count = sum(len(r.entities_detected) for r in results)
        r4.metric("PII Entities Found", pii_count)
        errors = sum(1 for r in results if r.error)
        r5.metric("Errors", errors, delta=None if errors == 0 else f"{errors} failed")

        if cfg and cfg.pipeline_mode != "raw":
            etype_counts = Counter(
                e.entity_type for r in results for e in r.entities_detected
            )
            if etype_counts:
                st.markdown("**PII Entity Type Breakdown (last ingest)**")
                st.bar_chart(dict(etype_counts))

    st.markdown("### How LexiRedact Works")
    st.markdown("""
    | Step | Dual Mode | Pre-Redacted | Raw |
    |------|-----------|--------------|-----|
    | **1. Detect PII** | ✅ Presidio scans text | ✅ Presidio scans text | ❌ Skipped |
    | **2. Embed** | Original text → embedding | Sanitized text → embedding | Original text → embedding |
    | **3. Redact** | ✅ In parallel with embed | ✅ Sequential before embed | ❌ Skipped |
    | **4. Store** | Sanitized text + original embedding | Sanitized text + sanitized embedding | Original text + original embedding |
    | **Retrieval quality** | ⬆️ High (semantic from original) | ↔️ Medium (degraded by redaction) | ⬆️ High (but no privacy) |
    | **Privacy** | ✅ PII never stored | ✅ PII never stored | ❌ PII in database |
    """)

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE CONFIG PANEL (shared)
# ═══════════════════════════════════════════════════════════════════════════════

def _config_panel(key_prefix: str = "") -> dict:
    """Render full pipeline config UI. Returns config dict."""
    with st.expander("⚙️ Pipeline Configuration", expanded=False):
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Core Settings**")
            mode = st.selectbox(
                "Pipeline Mode",
                options=list(PIPELINE_MODES.keys()),
                format_func=lambda m: PIPELINE_MODES[m],
                key=f"{key_prefix}_mode",
            )
            collection = st.text_input(
                "Collection Name", value="lexiredact", key=f"{key_prefix}_collection",
                help="ChromaDB collection name. Different names = isolated namespaces.",
            )
            persist_dir = st.text_input("Persist Directory", value="./chroma_db", key=f"{key_prefix}_persist_dir")

            # ── EDIT 13-A: Updated Embedder section ───────────────────────────
            st.markdown("**Embedder**")
            embed_backend = st.selectbox(
                "Backend",
                ["sentence_transformers", "huggingface"],
                key=f"{key_prefix}_embed_backend",
                help="sentence_transformers: recommended for e5, BGE, MiniLM. huggingface: raw AutoModel with mean pooling.",
            )
            _default_models = {
                "sentence_transformers": "intfloat/e5-small-v2",
                "huggingface": "bert-base-uncased",
            }
            embed_model = st.text_input(
                "Model Name (HuggingFace Hub ID)",
                value=_default_models.get(embed_backend, "intfloat/e5-small-v2"),
                key=f"{key_prefix}_embed_model",
                help="Any model ID from HuggingFace Hub compatible with the selected backend.",
            )
            doc_prefix = st.text_input(
                "Document Prefix",
                value="passage: " if embed_backend == "sentence_transformers" else "",
                key=f"{key_prefix}_doc_prefix",
                help="Prepended to each chunk text during ingestion. Use 'passage: ' for e5 models. Leave blank for most others.",
            )
            query_prefix = st.text_input(
                "Query Prefix",
                value="query: " if embed_backend == "sentence_transformers" else "",
                key=f"{key_prefix}_query_prefix",
                help="Prepended to query strings at retrieval time. Use 'query: ' for e5 models.",
            )
            embed_batch = st.number_input("Embed Batch Size", 1, 256, 32, key=f"{key_prefix}_embed_batch")
            device = st.selectbox("Device", ["cpu", "cuda", "mps"], key=f"{key_prefix}_device")
            normalize = st.checkbox("Normalize Embeddings", True, key=f"{key_prefix}_normalize")

        with col_b:
            # ── EDIT 13-C: Updated PII section with NLP engine selector ───────
            st.markdown("**PII Detection**")
            entities = st.multiselect(
                "Entities to Detect", ALL_PII_ENTITIES,
                default=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "CREDIT_CARD", "IBAN_CODE"],
                key=f"{key_prefix}_entities",
            )
            nlp_engine = st.selectbox(
                "NLP Engine",
                ["spacy", "transformers", "stanza"],
                key=f"{key_prefix}_nlp_engine",
                help="spacy: default, fast. transformers: better recall (requires presidio-analyzer[transformers]). stanza: multilingual.",
            )
            if nlp_engine == "spacy":
                spacy_model = st.selectbox("spaCy Model", SPACY_MODELS, key=f"{key_prefix}_spacy")
                nlp_model_value = spacy_model
            else:
                spacy_model = "en_core_web_lg"  # default kept for backward compat
                nlp_model_value = st.text_input(
                    "NLP Model Name",
                    value="dslim/bert-base-NER" if nlp_engine == "transformers" else "en",
                    key=f"{key_prefix}_nlp_model",
                    help="HuggingFace model ID for transformers engine, or language code for stanza.",
                )
            score_threshold = st.slider(
                "Detection Score Threshold", 0.1, 1.0, 0.7, 0.05, key=f"{key_prefix}_threshold",
                help="Minimum Presidio confidence score for a span to be flagged as PII.",
            )
            pii_batch = st.number_input("PII Batch Size", 1, 64, 16, key=f"{key_prefix}_pii_batch")

            st.markdown("**Redis Cache**")
            cache_on = st.checkbox("Enable Redis Cache", False, key=f"{key_prefix}_cache_on")
            redis_url = st.text_input("Redis URL", "redis://localhost:6379", key=f"{key_prefix}_redis")
            ttl = st.number_input("TTL (seconds)", 60, 604800, 86400, key=f"{key_prefix}_ttl",
                                  disabled=not cache_on)

    # ── EDIT 13-B: Updated return dict ────────────────────────────────────────
    return dict(
        mode=mode, collection=collection, persist_dir=persist_dir,
        embed_backend=embed_backend, embed_model=embed_model,
        doc_prefix=doc_prefix, query_prefix=query_prefix,
        embed_batch=embed_batch, device=device, normalize=normalize,
        entities=entities, spacy_model=spacy_model, nlp_engine=nlp_engine,
        nlp_model=nlp_model_value, score_threshold=score_threshold, pii_batch=pii_batch,
        cache_on=cache_on, redis_url=redis_url, ttl=ttl,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: INGEST
# ═══════════════════════════════════════════════════════════════════════════════

def page_ingest() -> None:
    if not _vs_guard(): return

    st.title("📥 Ingest")
    st.caption("Upload a JSON dataset, map schema fields, configure the pipeline, and run ingestion.")
    st.divider()

    st.markdown("### 1. Data Source")
    data_source = st.radio(
        "Choose dataset",
        ["Upload JSON file", "Use built-in sample dataset", "Paste JSON directly"],
        horizontal=True,
    )

    records: list[dict] | None = None

    if data_source == "Upload JSON file":
        uploaded = st.file_uploader(
            "Upload JSON file — array of objects `[{id, text, ...}, ...]`", type=["json"],
            help="Each object must have a unique identifier field and a text field.",
        )
        if uploaded:
            records = _parse_uploaded_json(uploaded)

    elif data_source == "Use built-in sample dataset":
        records = SAMPLE_DATASET
        st.success(f"Loaded {len(records)} sample chunks covering billing, HR, medical, IT security, and legal topics.")

    else:
        raw_json = st.text_area(
            "Paste JSON array",
            value='[\n  {"id": "doc_001", "text": "Your text here..."}\n]',
            height=150,
        )
        if st.button("Parse JSON"):
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    records = parsed
                    st.success(f"Parsed {len(records)} records.")
                else:
                    st.error("Must be a JSON array.")
            except json.JSONDecodeError as e:
                st.error(f"Parse error: {e}")

    if records is None:
        st.info("Select a data source above to continue.")
        return

    st.markdown(f"**Preview** — {len(records):,} records detected")
    with st.expander("Show first 5 records"):
        st.json(records[:5])

    all_fields = _detect_fields(records)

    st.markdown("### 2. Schema Mapping")
    c1, c2, c3 = st.columns(3)
    with c1:
        id_field = st.selectbox("ID Field", all_fields,
                                index=all_fields.index("id") if "id" in all_fields else 0)
    with c2:
        text_field = st.selectbox("Text Field", all_fields,
                                  index=all_fields.index("text") if "text" in all_fields else 0)
    with c3:
        meta_candidates = [f for f in all_fields if f not in (id_field, text_field)]
        metadata_fields = st.multiselect("Metadata Fields (optional)", meta_candidates)

    missing_ids  = [r for r in records if id_field not in r or not str(r.get(id_field, "")).strip()]
    missing_text = [r for r in records if text_field not in r or not str(r.get(text_field, "")).strip()]

    v1, v2 = st.columns(2)
    with v1:
        if missing_ids:
            st.warning(f"⚠️ {len(missing_ids)} record(s) have missing/empty ID field `{id_field}`")
        else:
            st.success(f"✅ ID field `{id_field}` present in all records")
    with v2:
        if missing_text:
            st.warning(f"⚠️ {len(missing_text)} record(s) have missing/empty text field `{text_field}`")
        else:
            st.success(f"✅ Text field `{text_field}` present in all records")

    st.markdown("### 3. Pipeline Configuration")
    cfg_vals = _config_panel("ingest")

    st.markdown("### 4. Run Ingestion")
    valid_records = [r for r in records if id_field in r and text_field in r
                     and str(r.get(text_field, "")).strip()]

    st.info(f"**{len(valid_records):,}** valid records will be ingested  "
            f"(skipping {len(records) - len(valid_records)} invalid).")

    if st.button("▶ Run Ingestion", type="primary", disabled=len(valid_records) == 0):
        # ── EDIT 13-E: Updated _build_config() call ───────────────────────────
        config = _build_config(
            mode=cfg_vals["mode"], collection=cfg_vals["collection"],
            entities=cfg_vals["entities"],
            spacy_model=cfg_vals["spacy_model"],
            nlp_engine=cfg_vals["nlp_engine"],
            nlp_model=cfg_vals["nlp_model"],
            score_threshold=cfg_vals["score_threshold"], batch_size=cfg_vals["pii_batch"],
            embed_backend=cfg_vals["embed_backend"],
            embed_model=cfg_vals["embed_model"],
            doc_prefix=cfg_vals["doc_prefix"],
            query_prefix=cfg_vals["query_prefix"],
            embed_batch=cfg_vals["embed_batch"],
            device=cfg_vals["device"], normalize=cfg_vals["normalize"],
            cache_enabled=cfg_vals["cache_on"], redis_url=cfg_vals["redis_url"],
            ttl=cfg_vals["ttl"], persist_dir=cfg_vals["persist_dir"],
            id_field=id_field, text_field=text_field, metadata_fields=metadata_fields,
        )

        raw_chunks = [
            {id_field: str(r[id_field]), text_field: str(r[text_field]),
             **{mf: r[mf] for mf in metadata_fields if mf in r}}
            for r in valid_records
        ]

        progress = st.progress(0, text="Initialising pipeline…")
        status_area = st.empty()

        try:
            pipeline = LexiredactPipeline(config)
            t_start = time.perf_counter()
            status_area.info("⚙️ Running ingestion (this may take a moment for first run — model loads lazily)…")
            results = pipeline.ingest(raw_chunks)
            elapsed = time.perf_counter() - t_start

            progress.progress(1.0, text="Complete!")
            st.session_state.ingest_results = results
            st.session_state.ingest_config = config
            st.session_state.ingest_dataset = valid_records
            st.session_state.ingest_collection = cfg_vals["collection"]

            status_area.empty()
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Chunks Processed", len(results))
            s2.metric("Total Elapsed", f"{elapsed:.1f}s")

            lats = [r.latency_ms for r in results]
            avg_l = statistics.mean(lats) if lats else 0.0
            std_l = statistics.stdev(lats) if len(lats) >= 2 else 0.0
            s3.metric("Avg Latency / Chunk", f"{avg_l:.1f} ms",
                      delta=f"±{std_l:.1f} ms std",
                      help="Mean ± std dev. Excludes model initialization (handled by warmup).")
            s4.metric("Cache Hits", f"{sum(1 for r in results if r.cache_hit)}/{len(results)}")
            pii_n = sum(len(r.entities_detected) for r in results)
            s5.metric("PII Entities Detected", pii_n)

            with st.expander("Per-chunk results", expanded=False):
                rows = []
                for r in results:
                    row = {
                        "Chunk ID": r.chunk_id,
                        "Mode": r.pipeline_mode,
                        "PII Entities": len(r.entities_detected),
                        "Latency (ms)": round(r.latency_ms, 2),
                        "Cache Hit": "✓" if r.cache_hit else "—",
                        "Stored": "✓" if r.embedding_stored else "✗",
                        "Error": r.error or "",
                    }
                    if r.stage_latencies:
                        for k, v in r.stage_latencies.items():
                            row[k] = f"{v:.1f}"
                    rows.append(row)
                st.dataframe(rows, use_container_width=True, hide_index=True)

            errors = [r for r in results if r.error]
            if errors:
                st.warning(f"⚠️ {len(errors)} chunk(s) had errors. See table above.")

        except Exception as exc:
            progress.empty()
            status_area.empty()
            st.error(f"**Ingestion failed:** {exc}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: PII INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def page_inspector() -> None:
    if not _vs_guard(): return

    st.title("🔬 PII Inspector")
    st.caption("Analyze individual chunks or a small batch. See exactly what PII is detected and how the text is sanitized.")
    st.divider()

    with st.expander("⚙️ Detection Settings", expanded=False):
        i1, i2, i3, i4 = st.columns(4)
        with i1:
            mode = st.selectbox("Pipeline Mode", list(PIPELINE_MODES.keys()),
                                format_func=lambda m: PIPELINE_MODES[m], key="ins_mode")
        with i2:
            entities = st.multiselect("Entities", ALL_PII_ENTITIES,
                                      default=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                                               "LOCATION", "CREDIT_CARD", "IBAN_CODE"],
                                      key="ins_entities")
        with i3:
            spacy = st.selectbox("spaCy Model", SPACY_MODELS, key="ins_spacy")
        with i4:
            threshold = st.slider("Score Threshold", 0.1, 1.0, 0.7, 0.05, key="ins_threshold")
        collection = st.text_input("Store To Collection", "vs_inspector", key="ins_collection")

    input_mode = st.radio("Input Mode", ["Single Chunk", "Batch (up to 20)"], horizontal=True)

    chunks_to_run: list[dict] = []

    if input_mode == "Single Chunk":
        chunk_id = st.text_input("Chunk ID", "chunk_001", key="ins_single_id")
        chunk_text = st.text_area(
            "Text", value=SAMPLE_DATASET[0]["text"], height=120, key="ins_single_text",
            placeholder="Enter text to analyze…",
        )
        if chunk_id.strip() and chunk_text.strip():
            chunks_to_run = [{"id": chunk_id, "text": chunk_text}]
    else:
        batch_json = st.text_area(
            'Batch JSON — array of `{"id": "...", "text": "..."}`',
            value=json.dumps([{"id": s["id"], "text": s["text"]} for s in SAMPLE_DATASET[:3]], indent=2),
            height=200, key="ins_batch",
        )
        try:
            parsed = json.loads(batch_json)
            if isinstance(parsed, list) and len(parsed) <= 20:
                chunks_to_run = parsed
                st.caption(f"{len(chunks_to_run)} chunks ready")
            else:
                st.warning("Must be a JSON array with ≤ 20 items.")
        except json.JSONDecodeError as e:
            st.error(f"JSON error: {e}")

    run_btn = st.button("▶ Analyze", type="primary", disabled=not chunks_to_run)

    if run_btn and chunks_to_run:
        config = _build_config(
            mode=mode, collection=collection, entities=entities,
            spacy_model=spacy, nlp_engine="spacy", nlp_model=spacy,
            score_threshold=threshold, batch_size=16,
            embed_backend="sentence_transformers",
            embed_model="intfloat/e5-small-v2",
            doc_prefix="passage: ", query_prefix="query: ",
            embed_batch=32, device="cpu", normalize=True, cache_enabled=False,
            redis_url="redis://localhost:6379", ttl=86400, persist_dir="./chroma_db",
        )
        with st.spinner("Running pipeline…"):
            try:
                pipeline = LexiredactPipeline(config)
                results = pipeline.ingest(chunks_to_run)
                st.session_state.inspector_results = list(zip(chunks_to_run, results))
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    if not st.session_state.inspector_results:
        st.info("Run analysis above to see results here.")
        return

    for raw, result in st.session_state.inspector_results:
        original_text = raw.get("text", "")

        with st.container():
            st.markdown(f"#### `{result.chunk_id}`")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Pipeline Mode", result.pipeline_mode)
            m2.metric("Latency", f"{result.latency_ms:.1f} ms")
            m3.metric("PII Entities", len(result.entities_detected))
            m4.metric("Cache Hit", "Yes" if result.cache_hit else "No")

            col_orig, col_san = st.columns(2)

            with col_orig:
                st.markdown("**Original Text** — PII spans highlighted")
                highlighted = _highlight_pii(original_text, result.entities_detected)
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:14px;line-height:1.7;font-size:0.93em;">{highlighted}</div>',
                    unsafe_allow_html=True,
                )

            with col_san:
                stored_text = result.sanitized_text or original_text
                label = "Sanitized Text" if result.sanitized_text else "Stored Text (no redaction in raw mode)"
                st.markdown(f"**{label}** — redacted placeholders highlighted")
                redacted_html = _highlight_redacted(stored_text)
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:14px;line-height:1.7;font-size:0.93em;">{redacted_html}</div>',
                    unsafe_allow_html=True,
                )

            if result.entities_detected:
                with st.expander(f"Detected Entities ({len(result.entities_detected)})", expanded=True):
                    ent_rows = [
                        {
                            "Entity Type": e.entity_type, "Value": e.text,
                            "Confidence": f"{e.score:.3f}", "Start": e.start, "End": e.end,
                        }
                        for e in sorted(result.entities_detected, key=lambda x: x.start)
                    ]
                    st.dataframe(ent_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No PII detected in this chunk." if mode != "raw" else "PII detection skipped (raw mode).")

            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: QUERY LAB
# ═══════════════════════════════════════════════════════════════════════════════

def page_query_lab() -> None:
    if not _vs_guard(): return

    st.title("🔍 Query Lab")
    st.caption("Semantic search over ingested collections. Results filtered by cosine distance threshold — only genuinely relevant chunks are shown.")
    st.divider()

    collections = _get_collections()
    if not collections:
        st.warning("No collections found. Go to **📥 Ingest** first to add data.", icon="⚠️")
        return

    q1, q2 = st.columns([2, 1])
    with q1:
        selected_collection = st.selectbox("Search Collection", collections)
        count = _collection_count(selected_collection)
        st.caption(f"{count:,} vectors in this collection")
    with q2:
        embed_model = st.text_input("Model Name", "intfloat/e5-small-v2", key="q_embed_model",
                                    help="Must match the model used during ingestion.")
        persist_dir = st.text_input("Persist Dir", "./chroma_db", key="q_persist")

    st.divider()

    query_text = st.text_input("Search Query",
                               placeholder="e.g. Who contacted billing about an overcharge?",
                               key="q_query")

    qa, qb, qc = st.columns(3)
    with qa:
        top_k = st.slider("Max Results to Retrieve (K)", 1, 20, 10, key="q_topk")
    with qb:
        dist_threshold = st.slider(
            "Distance Threshold", 0.0, 1.5, 0.6, 0.05, key="q_threshold",
        )
    with qc:
        st.markdown("**Threshold Guide**")
        st.markdown("""
        <small>
        🟢 <b>< 0.30</b> Excellent<br>
        🔵 <b>0.30–0.50</b> Good<br>
        🟡 <b>0.50–0.70</b> Marginal<br>
        🔴 <b>> 0.70</b> Poor / Unrelated
        </small>
        """, unsafe_allow_html=True)

    run_query = st.button("🔍 Search", type="primary", disabled=not query_text.strip())

    if run_query and query_text.strip():
        try:
            config = LexiredactConfig(
                store=StoreConfig(collection_name=selected_collection, persist_directory=persist_dir),
                embedder=EmbedderConfig(model_name=embed_model),
            )
            with st.spinner("Embedding query and searching…"):
                # ── EDIT 13-E: use create_embedder registry ───────────────────
                embedder = create_embedder(config.embedder)
                store = ChromaStore(config.store, embedder.get_dimension())
                query_vectors = embedder.query_embed([query_text])
                hits = store.query(query_vectors[0], top_k=top_k)
            st.session_state.query_hits = hits
            st.session_state.query_collection = selected_collection
        except Exception as exc:
            st.error(f"Query failed: {exc}")

    if not st.session_state.query_hits:
        if not run_query:
            st.info("Enter a query above and click Search.")
        return

    hits = st.session_state.query_hits
    relevant = [h for h in hits if h["distance"] <= dist_threshold]
    filtered_out = [h for h in hits if h["distance"] > dist_threshold]

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Retrieved (K)", len(hits))
    r2.metric("Passed Threshold", len(relevant))
    r3.metric("Filtered Out", len(filtered_out))
    if relevant:
        best_dist = min(h["distance"] for h in relevant)
        r4.metric("Best Distance", f"{best_dist:.4f}")
    else:
        r4.metric("Best Distance", "—")

    st.divider()

    if not relevant:
        st.error(
            f"**No relevant results found for this query.**\n\n"
            f"All {len(hits)} retrieved results exceeded the distance threshold of **{dist_threshold}**. "
            f"Try: Lower the threshold · Rephrase the query · Ingest more relevant data",
            icon="🔍",
        )
        if filtered_out:
            with st.expander(f"Show {len(filtered_out)} discarded results (above threshold)"):
                for h in filtered_out:
                    text = h["metadata"].get("text", "")
                    st.markdown(
                        f'<div class="result-card" style="opacity:0.5;">'
                        f'<b><code>{h["id"]}</code></b> &nbsp;'
                        f'{_distance_badge(h["distance"])}'
                        f'<div style="margin-top:8px;font-size:0.9em;color:#8b949e;">{_highlight_redacted(text)}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        return

    st.markdown(f"### {len(relevant)} Relevant Result(s) — sorted by similarity")

    for rank, hit in enumerate(relevant, 1):
        text = hit["metadata"].get("text", "")
        meta = {k: v for k, v in hit["metadata"].items() if k != "text"}
        dist = hit["distance"]

        col_rank, col_body = st.columns([1, 9])
        with col_rank:
            color = _distance_color(dist)
            st.markdown(
                f'<div style="text-align:center;padding-top:12px;">'
                f'<div style="font-size:28px;font-weight:700;color:{color};font-family:IBM Plex Mono;">#{rank}</div>'
                f'<div style="font-size:11px;color:{color};font-weight:600;">{dist:.4f}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_body:
            st.markdown(
                f'<div class="result-card">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                f'<code style="font-size:13px;color:#c9d1d9;">{hit["id"]}</code>'
                f'{_distance_badge(dist)}'
                f'</div>'
                f'<div style="line-height:1.7;font-size:0.92em;">{_highlight_redacted(text)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if meta:
                with st.expander("Metadata"):
                    st.json(meta)

    if filtered_out:
        with st.expander(f"🗑️ {len(filtered_out)} result(s) hidden by threshold ({dist_threshold})"):
            for h in filtered_out:
                text = h["metadata"].get("text", "")
                st.markdown(
                    f'`{h["id"]}` — distance {h["distance"]:.4f} &nbsp; '
                    f'{_distance_badge(h["distance"])}'
                    f'<div style="font-size:0.85em;color:#8b949e;margin:4px 0 8px 0;">{_highlight_redacted(text)[:200]}…</div>',
                    unsafe_allow_html=True,
                )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: COMPARATOR
# ═══════════════════════════════════════════════════════════════════════════════

def page_comparator() -> None:
    if not _vs_guard(): return

    st.title("⚖️ Comparator")
    st.caption("Run the same dataset through multiple pipeline modes and compare PII handling, stored text, and latency side-by-side.")
    st.divider()

    st.markdown("### Dataset")
    cmp_src = st.radio("Source", ["Built-in Sample", "Upload JSON"], horizontal=True)

    records: list[dict] = []
    id_field = "id"
    text_field = "text"

    if cmp_src == "Built-in Sample":
        records = SAMPLE_DATASET
        st.success(f"Using {len(records)} built-in sample chunks.")
    else:
        up = st.file_uploader("Upload JSON", type=["json"], key="cmp_upload")
        if up:
            parsed = _parse_uploaded_json(up)
            if parsed:
                records = parsed
                all_fields = _detect_fields(records)
                f1, f2 = st.columns(2)
                with f1:
                    id_field = st.selectbox("ID Field", all_fields,
                                            index=all_fields.index("id") if "id" in all_fields else 0,
                                            key="cmp_id")
                with f2:
                    text_field = st.selectbox("Text Field", all_fields,
                                              index=all_fields.index("text") if "text" in all_fields else 0,
                                              key="cmp_text")

    if not records:
        st.info("Select a dataset to continue.")
        return

    max_chunks = st.slider("Max Chunks to Compare", 3, min(50, len(records)), min(8, len(records)))
    records = records[:max_chunks]

    st.markdown("### Modes to Compare")
    m1, m2, m3 = st.columns(3)
    run_raw  = m1.checkbox("⚪ Raw", True)
    run_pre  = m2.checkbox("🔵 Pre-Redacted", True)
    run_dual = m3.checkbox("🟢 Dual", True)

    selected_modes = [m for m, sel in [("raw", run_raw), ("preredacted", run_pre), ("dual", run_dual)] if sel]

    if not selected_modes:
        st.warning("Select at least one mode.")
        return

    with st.expander("⚙️ PII / Embedder Settings"):
        p1, p2, p3 = st.columns(3)
        with p1:
            cmp_entities = st.multiselect("Entities", ALL_PII_ENTITIES,
                                          default=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                                                   "LOCATION", "CREDIT_CARD"],
                                          key="cmp_ents")
        with p2:
            cmp_spacy = st.selectbox("spaCy Model", SPACY_MODELS, key="cmp_spacy")
        with p3:
            cmp_threshold = st.slider("Score Threshold", 0.1, 1.0, 0.7, 0.05, key="cmp_thr")

    st.divider()
    run_btn = st.button("▶ Run Comparison", type="primary")

    if run_btn:
        st.session_state.compare_results = {}
        st.session_state.compare_retrieval_metrics = {}
        raw_chunks = [
            {id_field: str(r[id_field]), text_field: str(r[text_field])}
            for r in records if id_field in r and text_field in r
        ]

        overall_progress = st.progress(0)
        for mode_idx, mode in enumerate(selected_modes):
            overall_progress.progress(mode_idx / len(selected_modes),
                                      text=f"Running mode: {mode}…")
            # ── EDIT 13-E: Updated _build_config() call ───────────────────────
            config = _build_config(
                mode=mode, collection=f"vs_cmp_{mode}",
                entities=cmp_entities, spacy_model=cmp_spacy,
                nlp_engine="spacy", nlp_model=cmp_spacy,
                score_threshold=cmp_threshold, batch_size=16,
                embed_backend="sentence_transformers",
                embed_model="intfloat/e5-small-v2",
                doc_prefix="passage: ", query_prefix="query: ",
                embed_batch=32, device="cpu", normalize=True, cache_enabled=False,
                redis_url="redis://localhost:6379", ttl=86400, persist_dir="./chroma_db",
                id_field=id_field, text_field=text_field,
            )
            try:
                pipeline = LexiredactPipeline(config)
                results = pipeline.ingest(raw_chunks)
                st.session_state.compare_results[mode] = results
            except Exception as exc:
                st.error(f"Mode `{mode}` failed: {exc}")

        overall_progress.progress(1.0, text="Comparison complete!")
        st.session_state.compare_dataset = raw_chunks

    if not st.session_state.compare_results:
        st.info("Click **Run Comparison** above.")
        return

    compare = st.session_state.compare_results
    raw_chunks = st.session_state.compare_dataset or []

    st.markdown("### Mode Summary")
    summary_cols = st.columns(len(compare))
    for col, (mode, results) in zip(summary_cols, compare.items()):
        lats = [r.latency_ms for r in results]
        pii = sum(len(r.entities_detected) for r in results)
        color = MODE_COLORS.get(mode, "#8b949e")
        avg_l = statistics.mean(lats) if lats else 0.0
        std_l = statistics.stdev(lats) if len(lats) >= 2 else 0.0
        p95_l = _p95_latency(lats)

        stage_totals: dict[str, float] = defaultdict(float)
        stage_counts: dict[str, int] = defaultdict(int)
        for r in results:
            if r.stage_latencies:
                for k, v in r.stage_latencies.items():
                    stage_totals[k] += v
                    stage_counts[k] += 1
        avg_stage = {k: stage_totals[k] / stage_counts[k] for k in stage_totals if stage_counts[k] > 0}
        stage_html = _render_stage_breakdown_html(avg_stage, mode)

        with col:
            st.markdown(
                f'<div style="background:#161b22;border:2px solid {color};border-radius:10px;padding:16px;">'
                f'<div style="font-size:20px;font-weight:700;color:{color};text-align:center;">'
                f'{MODE_ICONS.get(mode,"")} {mode.upper()}</div>'
                f'<div style="margin-top:10px;color:#c9d1d9;font-size:13px;">'
                f'Avg: <b>{avg_l:.1f} ms</b> ± {std_l:.1f} ms</div>'
                f'<div style="color:#c9d1d9;font-size:13px;">p95: <b>{p95_l:.1f} ms</b></div>'
                f'<div style="color:#c9d1d9;font-size:13px;">PII entities: <b>{pii}</b></div>'
                f'<div style="color:#c9d1d9;font-size:13px;">Chunks: <b>{len(results)}</b></div>'
                f'<div style="margin-top:10px;">{stage_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("### Latency Distribution")
    try:
        import pandas as pd
        lat_rows = []
        for mode, results in compare.items():
            for r in results:
                lat_rows.append({"Chunk": r.chunk_id, "Mode": mode, "Latency (ms)": r.latency_ms})
        df = pd.DataFrame(lat_rows)
        pivot = df.pivot(index="Chunk", columns="Mode", values="Latency (ms)")
        st.bar_chart(pivot)
    except Exception:
        for mode, results in compare.items():
            lats = [r.latency_ms for r in results]
            st.write(f"**{mode}**: avg {statistics.mean(lats):.1f} ms" if lats else f"**{mode}**: no data")

    st.markdown("### Stage Latency Breakdown (mean ms per chunk)")
    has_any_stage_data = any(
        any(r.stage_latencies for r in results)
        for results in compare.values()
    )

    if has_any_stage_data:
        stage_rows = []
        for mode, results in compare.items():
            totals: dict[str, float] = defaultdict(float)
            counts: dict[str, int] = defaultdict(int)
            for r in results:
                if r.stage_latencies:
                    for k, v in r.stage_latencies.items():
                        totals[k] += v
                        counts[k] += 1
            row: dict[str, Any] = {"Mode": f"{MODE_ICONS.get(mode,'')} {mode}"}
            for k in totals:
                row[k] = f"{totals[k]/counts[k]:.1f} ms" if counts[k] > 0 else "—"
            total_ms = sum(totals[k] / counts[k] for k in totals if counts[k] > 0)
            row["Total (approx)"] = f"{total_ms:.1f} ms"
            stage_rows.append(row)
        st.dataframe(stage_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Stage latency data not available. Re-run ingestion to see stage breakdown.", icon="ℹ️")

    st.markdown("### Per-Chunk Output Comparison")
    for raw in raw_chunks:
        chunk_id = raw.get(id_field, raw.get("id", "?"))
        original_text = raw.get(text_field, raw.get("text", ""))

        with st.expander(f"Chunk: `{chunk_id}`", expanded=False):
            st.markdown(f"**Original:** {original_text}")
            st.divider()

            result_cols = st.columns(len(compare))
            for col, (mode, results) in zip(result_cols, compare.items()):
                r = next((x for x in results if x.chunk_id == str(chunk_id)), None)
                color = MODE_COLORS.get(mode, "#8b949e")
                with col:
                    st.markdown(
                        f'<div style="color:{color};font-weight:700;font-size:13px;margin-bottom:6px;">'
                        f'{MODE_ICONS.get(mode,"")} {mode.upper()}</div>',
                        unsafe_allow_html=True,
                    )
                    if r:
                        stored = r.sanitized_text or original_text
                        st.markdown(
                            f'<div style="background:#0d1117;border:1px solid {color}33;border-radius:6px;'
                            f'padding:10px;font-size:0.88em;line-height:1.6;">'
                            f'{_highlight_redacted(stored)}</div>',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"PII entities: {len(r.entities_detected)} · {r.latency_ms:.1f}ms")
                    else:
                        st.caption("No result")

    st.divider()
    st.markdown("### Retrieval Quality Evaluation")
    st.caption(
        "Test semantic retrieval quality across all modes side-by-side. "
        "Enter a query and (optionally) comma-separated relevant chunk IDs."
    )

    rq_col1, rq_col2 = st.columns([2, 1])
    with rq_col1:
        rq_query = st.text_input(
            "Retrieval Test Query",
            placeholder="e.g. Who contacted billing about an overcharge?",
            key="cmp_rq_query",
        )
    with rq_col2:
        rq_top_k = st.slider("Top K", 3, 10, 5, key="cmp_rq_topk")

    rq_relevant_raw = st.text_input(
        "Known Relevant Chunk IDs (optional, comma-separated)",
        placeholder="e.g. sample_001, sample_006",
        key="cmp_rq_relevant",
    )

    rq_run = st.button("🔍 Run Retrieval Evaluation", type="secondary",
                       disabled=not rq_query.strip() or not compare)

    if rq_run and rq_query.strip():
        relevant_ids: set[str] = set()
        if rq_relevant_raw.strip():
            relevant_ids = {s.strip() for s in rq_relevant_raw.split(",") if s.strip()}

        rq_results_by_mode: dict[str, dict] = {}
        try:
            embed_cfg = LexiredactConfig(
                embedder=EmbedderConfig(model_name="intfloat/e5-small-v2"),
                store=StoreConfig(),
            )
            # ── EDIT 13-E: use create_embedder registry ───────────────────────
            embedder = create_embedder(embed_cfg.embedder)
            q_vec = embedder.query_embed([rq_query])[0]

            for mode in compare:
                col_name = f"vs_cmp_{mode}"
                try:
                    store_cfg = LexiredactConfig(
                        store=StoreConfig(collection_name=col_name, persist_directory="./chroma_db"),
                        embedder=EmbedderConfig(),
                    )
                    store = ChromaStore(store_cfg.store, embedder.get_dimension())
                    hits = store.query(q_vec, top_k=rq_top_k)
                    retrieved_ids = [h["id"] for h in hits]

                    metrics: dict[str, Any] = {
                        "hits": hits,
                        "retrieved_ids": retrieved_ids,
                    }
                    if relevant_ids:
                        metrics["hit_at_5"]    = _hit_at_k(retrieved_ids, relevant_ids, rq_top_k)
                        metrics["recall_at_5"] = _recall_at_k(retrieved_ids, relevant_ids, rq_top_k)
                        metrics["ndcg_at_5"]   = _ndcg_at_k(retrieved_ids, relevant_ids, rq_top_k)
                        metrics["mrr"]         = _mrr_single(retrieved_ids, relevant_ids)
                    rq_results_by_mode[mode] = metrics
                except Exception as e:
                    rq_results_by_mode[mode] = {"error": str(e), "hits": [], "retrieved_ids": []}

            st.session_state.compare_retrieval_metrics = {
                "query": rq_query,
                "relevant_ids": sorted(relevant_ids),
                "results": rq_results_by_mode,
                "k": rq_top_k,
            }
        except Exception as e:
            st.error(f"Retrieval evaluation failed: {e}")

    rq_state = st.session_state.get("compare_retrieval_metrics", {})
    if rq_state and rq_state.get("results"):
        rq_data   = rq_state["results"]
        rq_k      = rq_state.get("k", 5)
        rq_rel    = set(rq_state.get("relevant_ids", []))
        has_rel   = bool(rq_rel)

        st.markdown(f'**Query:** `{rq_state.get("query","")}`')
        if has_rel:
            st.markdown(f'**Relevant IDs:** `{", ".join(sorted(rq_rel))}`')

        if has_rel:
            st.markdown("#### Retrieval Metrics")
            metric_rows = []
            for mode, data in rq_data.items():
                if "error" in data:
                    continue
                metric_rows.append({
                    "Mode": f"{MODE_ICONS.get(mode,'')} {mode}",
                    f"Hit@{rq_k}":    f"{data.get('hit_at_5', 0):.3f}",
                    f"Recall@{rq_k}": f"{data.get('recall_at_5', 0):.3f}",
                    f"nDCG@{rq_k}":   f"{data.get('ndcg_at_5', 0):.3f}",
                    "MRR":            f"{data.get('mrr', 0):.3f}",
                })
            if metric_rows:
                st.dataframe(metric_rows, use_container_width=True, hide_index=True)

        st.markdown("#### Ranked Results by Mode")
        result_cols = st.columns(len(rq_data))
        for col, (mode, data) in zip(result_cols, rq_data.items()):
            color = MODE_COLORS.get(mode, "#8b949e")
            with col:
                st.markdown(
                    f'<div style="color:{color};font-weight:700;font-size:13px;margin-bottom:8px;">'
                    f'{MODE_ICONS.get(mode,"")} {mode.upper()}</div>',
                    unsafe_allow_html=True,
                )
                if "error" in data:
                    st.error(f"Error: {data['error']}")
                    continue
                for rank, hit in enumerate(data["hits"], 1):
                    cid = hit["id"]
                    dist = hit["distance"]
                    text_snippet = hit["metadata"].get("text", "")[:120]
                    is_relevant = cid in rq_rel if has_rel else None
                    border_color = "#3fb950" if is_relevant else ("#f85149" if is_relevant is False else color + "33")
                    relevance_tag = ""
                    if is_relevant is True:
                        relevance_tag = '<span style="color:#3fb950;font-size:10px;font-weight:700;">✓ RELEVANT</span> '
                    elif is_relevant is False:
                        relevance_tag = '<span style="color:#8b949e;font-size:10px;">✗ not relevant</span> '
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {border_color};border-radius:6px;'
                        f'padding:8px;margin-bottom:6px;font-size:0.85em;">'
                        f'<div><b>#{rank}</b> <code>{cid}</code> {relevance_tag}</div>'
                        f'<div style="color:#8b949e;font-size:10px;margin-top:2px;">dist: {dist:.4f}</div>'
                        f'<div style="margin-top:4px;color:#c9d1d9;">{_highlight_redacted(text_snippet)}…</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def page_analytics() -> None:
    if not _vs_guard(): return

    st.title("📊 Analytics")
    st.caption("Pipeline performance metrics, PII entity distribution, and latency profiles.")
    st.divider()

    data_source = st.radio(
        "Data Source",
        ["Last Ingestion", "Last Comparison", "Upload Results JSON"],
        horizontal=True,
    )

    results_by_mode: dict[str, list] = {}
    retrieval_by_mode: dict[str, list[dict]] = {}

    if data_source == "Last Ingestion" and st.session_state.ingest_results:
        cfg = st.session_state.ingest_config
        mode = cfg.pipeline_mode if cfg else "unknown"
        results_by_mode[mode] = st.session_state.ingest_results

    elif data_source == "Last Comparison" and st.session_state.compare_results:
        results_by_mode = st.session_state.compare_results

    elif data_source == "Upload Results JSON":
        up = st.file_uploader(
            "Upload `{mode}_results.json` file (from eval/runners/compare.py)",
            type=["json"],
        )
        if up:
            try:
                payload = json.loads(up.read())
                mode_name = payload.get("mode", "unknown")

                from lexiredact.models.result import DetectedEntity, ProcessingResult

                results = []
                for r in payload.get("ingest_results", []):
                    entities = [DetectedEntity(**e) for e in r.get("entities_detected", [])]
                    results.append(ProcessingResult(
                        chunk_id=r["chunk_id"],
                        sanitized_text=r["sanitized_text"],
                        entities_detected=entities,
                        embedding_stored=r["embedding_stored"],
                        latency_ms=r["latency_ms"],
                        cache_hit=r["cache_hit"],
                        pipeline_mode=r["pipeline_mode"],
                        error=r.get("error"),
                        stage_latencies=r.get("stage_latencies"),
                    ))
                results_by_mode[mode_name] = results

                if payload.get("retrieval_results"):
                    retrieval_by_mode[mode_name] = payload["retrieval_results"]
                    st.success(
                        f"Loaded {len(results)} ingest results + "
                        f"{len(payload['retrieval_results'])} retrieval queries for mode '{mode_name}'."
                    )
                else:
                    st.success(f"Loaded {len(results)} ingest results for mode '{mode_name}'.")

            except Exception as e:
                st.error(f"Failed to load results: {e}")
    else:
        st.info("No data available. Run an ingestion or comparison first.", icon="ℹ️")
        return

    if not results_by_mode:
        st.info("No results to analyze.")
        return

    for mode, results in results_by_mode.items():
        color = MODE_COLORS.get(mode, "#8b949e")
        st.markdown(
            f'<h3 style="color:{color};">{MODE_ICONS.get(mode,"")} {mode.upper()} Mode</h3>',
            unsafe_allow_html=True,
        )

        if not results:
            st.caption("No results for this mode.")
            continue

        lats = [r.latency_ms for r in results]
        n = len(results)
        pii_counts = [len(r.entities_detected) for r in results]

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Chunks", n)

        avg_lat = statistics.mean(lats)
        std_lat = statistics.stdev(lats) if n >= 2 else 0.0
        k2.metric(
            "Avg Latency", f"{avg_lat:.1f} ms",
            delta=f"±{std_lat:.1f} ms std",
        )

        p95_lat = _p95_latency(lats)
        k3.metric("p95 Latency", f"{p95_lat:.1f} ms")
        k4.metric(
            "Cache Hit Rate",
            f"{sum(1 for r in results if r.cache_hit)/n*100:.0f}%",
        )
        k5.metric("Total PII Entities", sum(pii_counts))

        try:
            import pandas as pd
            st.markdown("**Latency Distribution (per chunk, ms)**")
            df_lat = pd.DataFrame({"Latency (ms)": lats, "Chunk": [r.chunk_id for r in results]})
            st.bar_chart(df_lat.set_index("Chunk")["Latency (ms)"])
            st.caption(
                f"Min: {min(lats):.1f}ms · Mean: {avg_lat:.1f}ms ± {std_lat:.1f}ms · "
                f"p95: {p95_lat:.1f}ms · Max: {max(lats):.1f}ms."
            )
        except Exception:
            pass

        stage_data = [r.stage_latencies for r in results if r.stage_latencies]
        if stage_data:
            with st.expander("⏱️ Stage Latency Breakdown (mean ms per stage)", expanded=True):
                totals: dict[str, float] = defaultdict(float)
                counts: dict[str, int] = defaultdict(int)
                for sl in stage_data:
                    for k, v in sl.items():
                        totals[k] += v
                        counts[k] += 1
                avg_stages = {k: totals[k] / counts[k] for k in totals if counts[k] > 0}

                stage_labels_display: dict[str, str] = {
                    "pii_ms":          "PII Detection",
                    "embed_redact_ms": "Embed + Redact (parallel ∥)",
                    "redact_ms":       "Redact (sequential)",
                    "embed_ms":        "Embed",
                    "store_ms":        "Store (ChromaDB upsert)",
                }
                stage_rows_display = [
                    {
                        "Stage": stage_labels_display.get(k, k),
                        "Avg (ms)": f"{v:.2f}",
                        "% of total": f"{v / sum(avg_stages.values()) * 100:.1f}%" if sum(avg_stages.values()) > 0 else "—",
                    }
                    for k, v in avg_stages.items()
                ]
                st.dataframe(stage_rows_display, use_container_width=True, hide_index=True)
                bar_html = _render_stage_breakdown_html(avg_stages, mode)
                st.markdown(bar_html, unsafe_allow_html=True)
        else:
            with st.expander("⏱️ Stage Latency Breakdown", expanded=False):
                st.info("Stage latency data not available. Re-ingest with the updated orchestrator.", icon="ℹ️")

        if mode != "raw":
            etype_counts = Counter(
                e.entity_type for r in results for e in r.entities_detected
            )
            if etype_counts:
                st.markdown("**PII Entity Type Distribution**")
                try:
                    df_pii = pd.DataFrame(
                        [{"Entity Type": k, "Count": v} for k, v in etype_counts.most_common()]
                    )
                    st.bar_chart(df_pii.set_index("Entity Type")["Count"])
                except Exception:
                    st.write(dict(etype_counts.most_common()))

                chunks_with_pii = sum(1 for c in pii_counts if c > 0)
                st.caption(
                    f"{chunks_with_pii}/{n} chunks contained PII. "
                    f"Average {statistics.mean(pii_counts):.1f} entities per chunk."
                )

            errors = [(r.chunk_id, r.error) for r in results if r.error]
            if errors:
                with st.expander(f"⚠️ {len(errors)} Chunk Error(s)"):
                    for cid, err in errors:
                        st.markdown(f"- `{cid}`: {err}")
            else:
                st.success("✅ All chunks processed without errors.")
        else:
            st.info("PII detection skipped in Raw mode — no entity analytics available.")

        if mode in retrieval_by_mode and retrieval_by_mode[mode]:
            rr_list = retrieval_by_mode[mode]
            st.markdown("**Retrieval Quality Metrics** *(from uploaded eval results)*")
            qr_pairs = [
                ([h for h in rr["retrieved_chunk_ids"]], set(rr["relevant_chunk_ids"]))
                for rr in rr_list
            ]
            rq_metrics = _compute_retrieval_metrics(qr_pairs, k=5)
            rm1, rm2, rm3, rm4 = st.columns(4)
            rm1.metric("Hit@5",    f"{rq_metrics['hit_at_k']:.3f}")
            rm2.metric("Recall@5", f"{rq_metrics['recall_at_k']:.3f}")
            rm3.metric("nDCG@5",   f"{rq_metrics['ndcg_at_k']:.3f}")
            rm4.metric("MRR",      f"{rq_metrics['mrr']:.3f}")

        st.divider()

    if len(results_by_mode) > 1:
        st.markdown("### Cross-Mode Comparison")
        try:
            import pandas as pd
            summary_rows = []
            for mode, results in results_by_mode.items():
                lats = [r.latency_ms for r in results]
                n = len(lats)
                avg_l = statistics.mean(lats) if lats else 0.0
                std_l = statistics.stdev(lats) if n >= 2 else 0.0
                p95_l = _p95_latency(lats)
                row: dict[str, Any] = {
                    "Mode": f"{MODE_ICONS.get(mode,'')} {mode}",
                    "Chunks": n,
                    "Avg Latency (ms)": f"{avg_l:.1f}",
                    "Std Dev (ms)": f"{std_l:.1f}",
                    "p95 Latency (ms)": f"{p95_l:.1f}",
                    "Total PII Entities": sum(len(r.entities_detected) for r in results),
                    "Cache Hit Rate": f"{sum(1 for r in results if r.cache_hit)/n*100:.0f}%",
                    "Errors": sum(1 for r in results if r.error),
                }
                if mode in retrieval_by_mode and retrieval_by_mode[mode]:
                    rr_list = retrieval_by_mode[mode]
                    qr_pairs = [
                        (rr["retrieved_chunk_ids"], set(rr["relevant_chunk_ids"]))
                        for rr in rr_list
                    ]
                    rq_m = _compute_retrieval_metrics(qr_pairs, k=5)
                    row["Hit@5"]    = f"{rq_m['hit_at_k']:.3f}"
                    row["Recall@5"] = f"{rq_m['recall_at_k']:.3f}"
                    row["nDCG@5"]   = f"{rq_m['ndcg_at_k']:.3f}"
                    row["MRR"]      = f"{rq_m['mrr']:.3f}"
                summary_rows.append(row)

            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    page = _sidebar()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Ingest":
        page_ingest()
    elif page == "PII Inspector":
        page_inspector()
    elif page == "Query Lab":
        page_query_lab()
    elif page == "Comparator":
        page_comparator()
    elif page == "Analytics":
        page_analytics()


if __name__ == "__main__":
    main()
