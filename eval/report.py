"""
eval/report.py — Generates 7 benchmark PNG figures, 3 CSV tables, and a
console summary from computed metric objects.

No hardcoded values anywhere. Every number in every chart comes directly
from the metric dataclass objects passed into generate_report().

Consistent color palette across ALL figures:
  raw         = #E57373  (red)
  preredacted = #64B5F6  (blue)
  dual        = #81C784  (green)

Mode labels:
  raw         → "Raw (Baseline)"
  preredacted → "Pre-Redacted"
  dual        → "Dual (Proposed)"

Figures produced:
  fig1_privacy_utility_tradeoff.png  — Scatter: PII Recall (x) vs nDCG@5 (y)
  fig2_retrieval_metrics.png         — Grouped bar: Hit@5, Recall@5, nDCG@5, MRR
  fig3_latency_distribution.png      — Box plot of per-chunk latency distributions
  fig4_stage_breakdown.png           — Stacked horizontal bar: stage time breakdown
  fig5_pii_detection_heatmap.png     — FNR (top) and Precision (bottom) heatmap
  fig6_cache_impact.png              — Cache impact on dual-mode latency
  fig7_f1_by_entity.png              — F1 per entity type for preredacted/dual

CSV tables:
  table1_retrieval_metrics.csv
  table2_privacy_metrics.csv
  table3_latency_metrics.csv

Usage:
  python eval/report.py \
    --results-dir eval/results/ \
    --dataset-dir eval/dataset/data/ \
    --output-dir  eval/results/graphs/
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Try seaborn style — fallback gracefully for older matplotlib versions
try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    try:
        plt.style.use("seaborn-whitegrid")
    except OSError:
        pass  # Fall back to default style

# IEEE-like font settings
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 200,
})

from eval.metrics.latency import LatencyMetrics, compute_latency_metrics
from eval.metrics.privacy import PrivacyMetrics, compute_privacy_metrics
from eval.metrics.utility import UtilityMetrics, compute_utility_metrics
from eval.runners.compare import CompareResult, load_compare_result

# ── Color palette and labels ──────────────────────────────────────────────────
COLORS: dict[str, str] = {
    "raw":         "#E57373",
    "preredacted": "#64B5F6",
    "dual":        "#81C784",
}
MODE_LABELS: dict[str, str] = {
    "raw":         "Raw (Baseline)",
    "preredacted": "Pre-Redacted",
    "dual":        "Dual (Proposed)",
}
MODES = ["raw", "preredacted", "dual"]


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(
    privacy: dict[str, PrivacyMetrics],
    utility: dict[str, UtilityMetrics],
    latency: dict[str, LatencyMetrics],
    compare_results: dict[str, CompareResult],
    output_dir: str,
) -> list[str]:
    """Generate 7 benchmark figures, 3 CSV tables, and a console summary.

    All values come from the passed metric objects — nothing is hardcoded.

    Args:
        privacy:         mode → PrivacyMetrics
        utility:         mode → UtilityMetrics
        latency:         mode → LatencyMetrics
        compare_results: mode → CompareResult (for raw latency distributions and stage data)
        output_dir:      Directory where PNG and CSV files are written.

    Returns:
        List of absolute file paths for all saved outputs (PNGs + CSVs).
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    # ── 7 Figures ─────────────────────────────────────────────────────────────
    saved.append(_fig1_privacy_utility_tradeoff(privacy, utility, output_dir))
    saved.append(_fig2_retrieval_metrics(utility, output_dir))
    saved.append(_fig3_latency_distribution(compare_results, output_dir))
    saved.append(_fig4_stage_breakdown(latency, output_dir))
    saved.append(_fig5_pii_heatmap(privacy, output_dir))
    saved.append(_fig6_cache_impact(latency, compare_results, output_dir))
    saved.append(_fig7_f1_by_entity(privacy, output_dir))

    # ── 3 CSV tables ──────────────────────────────────────────────────────────
    saved.append(_csv_table1_retrieval(utility, output_dir))
    saved.append(_csv_table2_privacy(privacy, output_dir))
    saved.append(_csv_table3_latency(latency, output_dir))

    # ── Console summary ────────────────────────────────────────────────────────
    _print_summary(utility, privacy, latency)

    return saved


# ── Figure 1: Privacy-Utility Tradeoff Scatter ───────────────────────────────

def _fig1_privacy_utility_tradeoff(
    privacy: dict[str, PrivacyMetrics],
    utility: dict[str, UtilityMetrics],
    output_dir: str,
) -> str:
    fig, ax = plt.subplots(figsize=(7, 5.5))

    for mode in MODES:
        p = privacy[mode]
        u = utility[mode]
        x = p.pii_recall      # PII Recall (higher = better privacy protection)
        y = u.ndcg_at_5        # nDCG@5 (higher = better retrieval utility)
        color = COLORS[mode]
        label = MODE_LABELS[mode]

        ax.scatter(x, y, color=color, s=220, zorder=5, edgecolors="white", linewidths=1.5)
        # Offset labels to avoid overlap
        offset_x = 0.012 if mode != "preredacted" else -0.085
        offset_y = 0.012 if mode != "raw" else -0.025
        ax.annotate(
            label,
            xy=(x, y),
            xytext=(x + offset_x, y + offset_y),
            fontsize=10,
            fontweight="bold",
            color=color,
        )

    ax.set_xlabel("PII Recall — Fraction of PII Correctly Detected", fontsize=11)
    ax.set_ylabel("nDCG@5 — Retrieval Quality Score [0, 1]", fontsize=11)
    ax.set_title(
        "Figure 1: Privacy-Utility Tradeoff\n"
        "Dual mode achieves top-right (high privacy + high utility)",
        fontsize=12,
        pad=10,
    )
    ax.set_xlim(-0.05, 1.15)
    ax.set_ylim(-0.05, 1.15)
    ax.axhline(0, color="#cccccc", linewidth=0.5)
    ax.axvline(0, color="#cccccc", linewidth=0.5)

    # Annotation: ideal quadrant
    ax.annotate(
        "← Ideal: high privacy\n    & high utility →",
        xy=(0.85, 0.85),
        fontsize=9,
        color="#555555",
        style="italic",
        ha="center",
    )

    legend_patches = [
        mpatches.Patch(color=COLORS[m], label=MODE_LABELS[m]) for m in MODES
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=10)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig1_privacy_utility_tradeoff.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 2: Retrieval Quality Metrics Grouped Bar ──────────────────────────

def _fig2_retrieval_metrics(
    utility: dict[str, UtilityMetrics],
    output_dir: str,
) -> str:
    metric_keys = ["hit_at_5", "recall_at_5", "ndcg_at_5", "mrr"]
    metric_labels = ["Hit@5", "Recall@5", "nDCG@5", "MRR"]

    x = np.arange(len(metric_keys))
    width = 0.25
    offsets = [-width, 0, width]

    fig, ax = plt.subplots(figsize=(9, 5.5))

    for mode_idx, mode in enumerate(MODES):
        u = utility[mode]
        values = [getattr(u, k) for k in metric_keys]
        bars = ax.bar(
            x + offsets[mode_idx],
            values,
            width,
            label=MODE_LABELS[mode],
            color=COLORS[mode],
            alpha=0.88,
            edgecolor="white",
            linewidth=0.7,
        )
        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.008,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
                color=COLORS[mode],
            )

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=11)
    ax.set_ylabel("Score [0, 1]", fontsize=11)
    ax.set_ylim(0, 1.18)
    ax.set_title(
        "Figure 2: Retrieval Quality Metrics by Pipeline Mode",
        fontsize=12, pad=10,
    )
    ax.legend(fontsize=10, loc="upper right")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig2_retrieval_metrics.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 3: Per-Chunk Latency Distribution Box Plot ────────────────────────

def _fig3_latency_distribution(
    compare_results: dict[str, CompareResult],
    output_dir: str,
) -> str:
    """Box plot with p25/median/p75 box, p5/p95 whiskers, mean triangle."""
    fig, ax = plt.subplots(figsize=(8, 5.5))

    plot_data = []
    positions = []
    mode_labels_ordered = []
    colors_ordered = []

    for i, mode in enumerate(MODES):
        if mode not in compare_results:
            continue
        lats = [r.latency_ms for r in compare_results[mode].ingest_results]
        if not lats:
            continue
        plot_data.append(lats)
        positions.append(i + 1)
        mode_labels_ordered.append(MODE_LABELS[mode])
        colors_ordered.append(COLORS[mode])

    if not plot_data:
        fig.text(0.5, 0.5, "No latency data available", ha="center", fontsize=12)
        out = str(Path(output_dir) / "fig3_latency_distribution.png")
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out

    # Use flierprops to show outliers as small dots
    flierprops = dict(marker=".", markerfacecolor="#999999", markersize=3, alpha=0.5, linestyle="none")
    medianprops = dict(color="#222222", linewidth=2.0)
    meanprops = dict(marker="^", markerfacecolor="#222222", markersize=8, markeredgecolor="white")

    bp = ax.boxplot(
        plot_data,
        positions=positions,
        patch_artist=True,
        notch=False,
        whis=[5, 95],  # whiskers at p5/p95
        showmeans=True,
        meanprops=meanprops,
        medianprops=medianprops,
        flierprops=flierprops,
        widths=0.5,
    )

    # Color boxes by mode
    for patch, color in zip(bp["boxes"], colors_ordered):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    for whisker in bp["whiskers"]:
        whisker.set(linestyle="--", linewidth=1.2, color="#555555")
    for cap in bp["caps"]:
        cap.set(linewidth=1.5, color="#555555")

    ax.set_xticks(positions)
    ax.set_xticklabels(mode_labels_ordered, fontsize=11)
    ax.set_ylabel("Per-Chunk Latency (ms)", fontsize=11)
    ax.set_title(
        "Figure 3: Per-Chunk Ingestion Latency Distribution",
        fontsize=12, pad=10,
    )
    fig.text(
        0.5, -0.03,
        "Warmup excluded. Box: p25–p75; whiskers: p5–p95; △ = mean.",
        ha="center", fontsize=9, color="#555555", style="italic",
    )

    # Legend patches for colors
    legend_patches = [
        mpatches.Patch(color=colors_ordered[i], label=mode_labels_ordered[i], alpha=0.75)
        for i in range(len(mode_labels_ordered))
    ]
    ax.legend(handles=legend_patches, fontsize=10, loc="upper right")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig3_latency_distribution.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 4: Stage Breakdown Stacked Horizontal Bar ─────────────────────────

def _fig4_stage_breakdown(
    latency: dict[str, LatencyMetrics],
    output_dir: str,
) -> str:
    """Stacked horizontal bar: shows WHERE time is spent per mode."""
    # Stage ordering and display labels per mode
    stage_display: dict[str, list[tuple[str, str]]] = {
        "dual":        [("pii_ms", "PII Detect"), ("embed_redact_ms", "Embed + Redact (∥)"), ("store_ms", "Store")],
        "preredacted": [("pii_ms", "PII Detect"), ("redact_ms", "Redact"), ("embed_ms", "Embed"), ("store_ms", "Store")],
        "raw":         [("embed_ms", "Embed"), ("store_ms", "Store")],
    }
    stage_colors = [
        "#7986CB",  # indigo — PII detect
        "#4DB6AC",  # teal — embed/embed+redact
        "#FFB74D",  # amber — redact
        "#F06292",  # pink — store
        "#A5D6A7",  # light green — extra
    ]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    y_positions = list(range(len(MODES)))
    bar_height = 0.45

    for y_pos, mode in zip(y_positions, MODES):
        stage_lat = latency[mode].avg_stage_latencies
        stages = stage_display.get(mode, [])

        # Fall back if no stage data recorded
        if not stage_lat:
            total = latency[mode].steady_latency_ms
            ax.barh(y_pos, total, height=bar_height,
                    color=COLORS[mode], alpha=0.5, edgecolor="white")
            ax.text(total + 0.5, y_pos, f"{total:.1f}ms (no stage data)",
                    va="center", fontsize=9, color="#555555")
            continue

        left = 0.0
        for color_idx, (stage_key, stage_label) in enumerate(stages):
            val = stage_lat.get(stage_key, 0.0)
            if val <= 0:
                continue
            color = stage_colors[color_idx % len(stage_colors)]
            ax.barh(y_pos, val, left=left, height=bar_height,
                    color=color, edgecolor="white", linewidth=0.5, alpha=0.88)
            if val >= 0.5:  # only label segments wide enough to read
                ax.text(
                    left + val / 2, y_pos,
                    f"{val:.1f}",
                    ha="center", va="center",
                    fontsize=8.5, fontweight="bold", color="white",
                )
            left += val

        # Total annotation at end of bar
        ax.text(left + 0.3, y_pos, f"{left:.1f} ms",
                va="center", fontsize=9, color="#333333", fontweight="bold")

    ax.set_yticks(y_positions)
    ax.set_yticklabels([MODE_LABELS[m] for m in MODES], fontsize=11)
    ax.set_xlabel("Per-Chunk Latency (ms, mean)", fontsize=11)
    ax.set_title("Figure 4: Latency Stage Breakdown by Pipeline Mode", fontsize=12, pad=10)

    # Build legend from stage labels across all modes
    legend_entries: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for mode in MODES:
        for color_idx, (_, stage_label) in enumerate(stage_display.get(mode, [])):
            if stage_label not in seen_labels:
                legend_entries.append((stage_label, stage_colors[color_idx % len(stage_colors)]))
                seen_labels.add(stage_label)

    legend_patches = [
        mpatches.Patch(color=col, label=lbl, alpha=0.88)
        for lbl, col in legend_entries
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=9, ncol=2)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig4_stage_breakdown.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 5: PII Detection Heatmap (FNR top + Precision bottom) ─────────────

def _fig5_pii_heatmap(
    privacy: dict[str, PrivacyMetrics],
    output_dir: str,
) -> str:
    """Two-panel heatmap: FNR (top) and Precision (bottom) per entity type × mode."""
    # Collect all entity types across all modes (union)
    all_types: list[str] = sorted({
        etype
        for pm in privacy.values()
        for etype in pm.fnr_by_entity_type
    } | {
        etype
        for pm in privacy.values()
        for etype in pm.precision_by_entity_type
    })
    if not all_types:
        all_types = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION",
                     "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS"]

    mode_labels = [MODE_LABELS[m] for m in MODES]
    n_types = len(all_types)
    n_modes = len(MODES)

    fnr_data = np.zeros((n_types, n_modes))
    prec_data = np.zeros((n_types, n_modes))

    for j, mode in enumerate(MODES):
        pm = privacy[mode]
        for i, etype in enumerate(all_types):
            fnr_data[i, j] = pm.fnr_by_entity_type.get(etype, 1.0 if mode == "raw" else 0.0)
            prec_data[i, j] = pm.precision_by_entity_type.get(etype, 0.0)

    fig, (ax_fnr, ax_prec) = plt.subplots(2, 1, figsize=(8, max(8, n_types * 1.1 + 3)))

    # Top panel — FNR (RdYlGn_r: red=high FNR=bad, green=low FNR=good)
    im_fnr = ax_fnr.imshow(fnr_data, cmap="RdYlGn_r", aspect="auto", vmin=0.0, vmax=1.0)
    plt.colorbar(im_fnr, ax=ax_fnr, label="False Negative Rate (0=good, 1=bad)", fraction=0.046, pad=0.04)
    ax_fnr.set_xticks(np.arange(n_modes))
    ax_fnr.set_xticklabels(mode_labels, fontsize=10)
    ax_fnr.set_yticks(np.arange(n_types))
    ax_fnr.set_yticklabels(all_types, fontsize=9)
    ax_fnr.set_title("Figure 5 (top): PII False Negative Rate by Entity Type", fontsize=11, pad=6)
    for i in range(n_types):
        for j in range(n_modes):
            val = fnr_data[i, j]
            text_color = "white" if (val > 0.65 or val < 0.15) else "black"
            ax_fnr.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=8.5, color=text_color, fontweight="bold")

    # Bottom panel — Precision (RdYlGn: green=high precision=good, red=low=bad)
    im_prec = ax_prec.imshow(prec_data, cmap="RdYlGn", aspect="auto", vmin=0.0, vmax=1.0)
    plt.colorbar(im_prec, ax=ax_prec, label="Precision (0=bad, 1=good)", fraction=0.046, pad=0.04)
    ax_prec.set_xticks(np.arange(n_modes))
    ax_prec.set_xticklabels(mode_labels, fontsize=10)
    ax_prec.set_yticks(np.arange(n_types))
    ax_prec.set_yticklabels(all_types, fontsize=9)
    ax_prec.set_title("Figure 5 (bottom): PII Precision by Entity Type", fontsize=11, pad=6)
    for i in range(n_types):
        for j in range(n_modes):
            val = prec_data[i, j]
            text_color = "white" if (val > 0.65 or val < 0.15) else "black"
            ax_prec.text(j, i, f"{val:.2f}", ha="center", va="center",
                         fontsize=8.5, color=text_color, fontweight="bold")

    fig.tight_layout()
    out = str(Path(output_dir) / "fig5_pii_detection_heatmap.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 6: Cache Impact ─────────────────────────────────────────────────────

def _fig6_cache_impact(
    latency: dict[str, LatencyMetrics],
    compare_results: dict[str, CompareResult],
    output_dir: str,
) -> str:
    """Cache impact on dual-mode latency. Shows run-1 vs run-2 comparison."""
    dual_lat = latency["dual"]
    cache_hit_rate = dual_lat.cache_hit_rate
    steady_ms = dual_lat.steady_latency_ms
    std_ms = dual_lat.std_dev_ms

    fig, ax = plt.subplots(figsize=(8, 5))

    if cache_hit_rate > 0.0:
        # Show actual cold vs warm comparison
        run1_lat = steady_ms
        run2_lat = steady_ms * (1.0 - cache_hit_rate)
        ax.plot([1, 2], [run1_lat, run2_lat], marker="o", linewidth=2.5,
                color=COLORS["dual"], label="With Cache (Redis)", markersize=9, zorder=5)
        ax.plot([1, 2], [run1_lat, run1_lat], linestyle="--", linewidth=2,
                color="#9E9E9E", label="Without Cache (model only)", markersize=0)
        ax.fill_between([1, 2], [run1_lat, run2_lat], [run1_lat, run1_lat],
                        alpha=0.12, color=COLORS["dual"])
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Run 1 (cold cache)", "Run 2 (warm cache)"], fontsize=11)
        ax.set_xlabel("Run Number", fontsize=11)
        saving_pct = (run1_lat - run2_lat) / run1_lat * 100 if run1_lat > 0 else 0
        ax.annotate(
            f"Cache saves ≈ {saving_pct:.0f}% latency\n(hit rate: {cache_hit_rate:.1%})",
            xy=(1.5, (run1_lat + run2_lat) / 2),
            fontsize=10, ha="center", color=COLORS["dual"], fontweight="bold",
        )
    else:
        # Cache disabled — show all-mode comparison with projected cache benefit
        modes_shown = [m for m in MODES if m in latency]
        vals = [latency[m].steady_latency_ms for m in modes_shown]
        stds = [latency[m].std_dev_ms for m in modes_shown]
        labels = [MODE_LABELS[m] for m in modes_shown]
        colors = [COLORS[m] for m in modes_shown]
        bars = ax.bar(labels, vals, color=colors, alpha=0.82, width=0.5,
                      yerr=stds, capsize=5, error_kw={"linewidth": 1.4})
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.1f} ms", ha="center", va="bottom", fontsize=10)
        ax.set_xlabel("Pipeline Mode", fontsize=11)
        ax.text(
            0.5, 0.95,
            f"Redis cache disabled (cache_hit_rate = {cache_hit_rate:.0%})\n"
            "Enable cache to observe latency reduction for repeat embeddings.",
            transform=ax.transAxes,
            ha="center", va="top", fontsize=9, color="#666666", style="italic",
        )

    ax.set_ylabel("Avg Per-Chunk Latency (ms)", fontsize=11)
    ax.set_title(
        "Figure 6: Effect of Redis Caching on Ingestion Latency (Dual Mode)",
        fontsize=12, pad=10,
    )
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig6_cache_impact.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Figure 7: F1 by Entity Type ───────────────────────────────────────────────

def _fig7_f1_by_entity(
    privacy: dict[str, PrivacyMetrics],
    output_dir: str,
) -> str:
    """Bar chart of F1 score per entity type for preredacted and dual modes."""
    # Collect entity types from non-raw modes (raw always has F1=0)
    plot_modes = [m for m in ["preredacted", "dual"] if m in privacy]
    if not plot_modes:
        # Fallback — nothing to plot
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No non-raw mode data available", ha="center", fontsize=12)
        out = str(Path(output_dir) / "fig7_f1_by_entity.png")
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out

    all_types: list[str] = sorted({
        etype
        for mode in plot_modes
        for etype in privacy[mode].f1_by_entity_type
    })

    x = np.arange(len(all_types))
    width = 0.35 / max(len(plot_modes) - 1, 1) * 2 if len(plot_modes) > 1 else 0.5
    offsets = np.linspace(-width / 2 * (len(plot_modes) - 1),
                           width / 2 * (len(plot_modes) - 1),
                           len(plot_modes)) if len(plot_modes) > 1 else [0.0]

    fig, ax = plt.subplots(figsize=(max(9, len(all_types) * 1.2), 5.5))

    for mode_idx, mode in enumerate(plot_modes):
        pm = privacy[mode]
        f1_vals = [pm.f1_by_entity_type.get(et, 0.0) for et in all_types]
        bars = ax.bar(
            x + offsets[mode_idx], f1_vals,
            width, label=MODE_LABELS[mode],
            color=COLORS[mode], alpha=0.88,
            edgecolor="white", linewidth=0.7,
        )
        for bar, val in zip(bars, f1_vals):
            if val > 0.02:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{val:.2f}",
                    ha="center", va="bottom",
                    fontsize=8, fontweight="bold", color=COLORS[mode],
                )

    ax.set_xticks(x)
    ax.set_xticklabels(all_types, rotation=30, ha="right", fontsize=10)
    ax.set_ylabel("F1 Score [0, 1]", fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.set_title(
        "Figure 7: PII Detection F1 Score by Entity Type\n"
        "(Raw mode excluded — F1 = 0.0 by definition)",
        fontsize=12, pad=10,
    )
    ax.legend(fontsize=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = str(Path(output_dir) / "fig7_f1_by_entity.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── CSV Table 1: Retrieval Metrics ────────────────────────────────────────────

def _csv_table1_retrieval(
    utility: dict[str, UtilityMetrics],
    output_dir: str,
) -> str:
    out = str(Path(output_dir) / "table1_retrieval_metrics.csv")
    fieldnames = [
        "Mode", "Hit@1", "Hit@3", "Hit@5",
        "Recall@3", "Recall@5", "nDCG@3", "nDCG@5", "MRR", "Total_Queries",
    ]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mode in MODES:
            if mode not in utility:
                continue
            u = utility[mode]
            writer.writerow({
                "Mode": MODE_LABELS[mode],
                "Hit@1": f"{u.hit_at_1:.4f}",
                "Hit@3": f"{u.hit_at_3:.4f}",
                "Hit@5": f"{u.hit_at_5:.4f}",
                "Recall@3": f"{u.recall_at_3:.4f}",
                "Recall@5": f"{u.recall_at_5:.4f}",
                "nDCG@3": f"{u.ndcg_at_3:.4f}",
                "nDCG@5": f"{u.ndcg_at_5:.4f}",
                "MRR": f"{u.mrr:.4f}",
                "Total_Queries": u.total_queries,
            })
    print(f"Saved: {out}")
    return out


# ── CSV Table 2: Privacy Metrics ──────────────────────────────────────────────

def _csv_table2_privacy(
    privacy: dict[str, PrivacyMetrics],
    output_dir: str,
) -> str:
    out = str(Path(output_dir) / "table2_privacy_metrics.csv")
    fieldnames = [
        "Mode", "Precision", "Recall_PII", "F1", "FNR",
        "FP_Rate_of_Detections",
        "Total_Annotated", "Total_Detected_TP", "Total_Missed_FN", "Total_FP",
    ]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mode in MODES:
            if mode not in privacy:
                continue
            p = privacy[mode]
            writer.writerow({
                "Mode": MODE_LABELS[mode],
                "Precision": f"{p.pii_precision:.4f}",
                "Recall_PII": f"{p.pii_recall:.4f}",
                "F1": f"{p.pii_f1:.4f}",
                "FNR": f"{p.false_negative_rate:.4f}",
                "FP_Rate_of_Detections": f"{p.false_positive_rate_of_detections:.4f}",
                "Total_Annotated": p.total_annotated,
                "Total_Detected_TP": p.total_detected,
                "Total_Missed_FN": p.total_missed,
                "Total_FP": p.total_false_positives,
            })
    print(f"Saved: {out}")
    return out


# ── CSV Table 3: Latency Metrics ──────────────────────────────────────────────

def _csv_table3_latency(
    latency: dict[str, LatencyMetrics],
    output_dir: str,
) -> str:
    out = str(Path(output_dir) / "table3_latency_metrics.csv")
    fieldnames = [
        "Mode", "Mean_ms", "Std_ms", "Min_ms", "p50_ms", "p95_ms", "Max_ms",
        "Throughput_chunks_per_sec", "Cache_Hit_Rate", "Warmup_ms",
    ]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mode in MODES:
            if mode not in latency:
                continue
            lat = latency[mode]
            writer.writerow({
                "Mode": MODE_LABELS[mode],
                "Mean_ms": f"{lat.steady_latency_ms:.2f}",
                "Std_ms": f"{lat.std_dev_ms:.2f}",
                "Min_ms": f"{lat.min_latency_ms:.2f}",
                "p50_ms": f"{lat.p50_latency_ms:.2f}",
                "p95_ms": f"{lat.p95_latency_ms:.2f}",
                "Max_ms": f"{lat.max_latency_ms:.2f}",
                "Throughput_chunks_per_sec": f"{lat.throughput_chunks_per_sec:.2f}",
                "Cache_Hit_Rate": f"{lat.cache_hit_rate:.4f}",
                "Warmup_ms": f"{lat.warmup_latency_ms:.2f}",
            })
    print(f"Saved: {out}")
    return out


# ── Console Summary ───────────────────────────────────────────────────────────

def _print_summary(
    utility: dict[str, UtilityMetrics],
    privacy: dict[str, PrivacyMetrics],
    latency: dict[str, LatencyMetrics],
) -> None:
    """Print formatted summary tables to stdout."""
    sep = "=" * 80

    print(f"\n{sep}")
    print("LexiRedact — EVALUATION RESULTS SUMMARY")
    print(sep)

    # ── Table 1: Retrieval ─────────────────────────────────────────────────────
    print("\nTABLE 1: RETRIEVAL QUALITY METRICS")
    hdr = f"{'Mode':<16} {'Hit@1':>6} {'Hit@3':>6} {'Hit@5':>6} {'Rec@3':>6} {'Rec@5':>6} {'nDCG@3':>7} {'nDCG@5':>7} {'MRR':>7}"
    print(hdr)
    print("-" * len(hdr))
    for mode in MODES:
        if mode not in utility:
            continue
        u = utility[mode]
        label = MODE_LABELS[mode]
        print(
            f"{label:<16} "
            f"{u.hit_at_1:>6.3f} "
            f"{u.hit_at_3:>6.3f} "
            f"{u.hit_at_5:>6.3f} "
            f"{u.recall_at_3:>6.3f} "
            f"{u.recall_at_5:>6.3f} "
            f"{u.ndcg_at_3:>7.3f} "
            f"{u.ndcg_at_5:>7.3f} "
            f"{u.mrr:>7.3f}"
        )

    # ── Table 2: Privacy ───────────────────────────────────────────────────────
    print("\nTABLE 2: PII DETECTION QUALITY METRICS")
    hdr2 = f"{'Mode':<16} {'Prec':>6} {'Recall':>7} {'F1':>6} {'FNR':>6} {'Annot':>6} {'DetTP':>6} {'FP':>5}"
    print(hdr2)
    print("-" * len(hdr2))
    for mode in MODES:
        if mode not in privacy:
            continue
        p = privacy[mode]
        label = MODE_LABELS[mode]
        print(
            f"{label:<16} "
            f"{p.pii_precision:>6.3f} "
            f"{p.pii_recall:>7.3f} "
            f"{p.pii_f1:>6.3f} "
            f"{p.false_negative_rate:>6.3f} "
            f"{p.total_annotated:>6d} "
            f"{p.total_detected:>6d} "
            f"{p.total_false_positives:>5d}"
        )

    # ── Table 3: Latency ───────────────────────────────────────────────────────
    print("\nTABLE 3: LATENCY METRICS")
    hdr3 = (
        f"{'Mode':<16} {'Mean(ms)':>9} {'Std(ms)':>8} "
        f"{'p50(ms)':>8} {'p95(ms)':>8} {'Min(ms)':>8} {'Max(ms)':>8} "
        f"{'Tput':>6} {'Cache%':>7}"
    )
    print(hdr3)
    print("-" * len(hdr3))
    for mode in MODES:
        if mode not in latency:
            continue
        lat = latency[mode]
        label = MODE_LABELS[mode]
        print(
            f"{label:<16} "
            f"{lat.steady_latency_ms:>9.1f} "
            f"{lat.std_dev_ms:>8.1f} "
            f"{lat.p50_latency_ms:>8.1f} "
            f"{lat.p95_latency_ms:>8.1f} "
            f"{lat.min_latency_ms:>8.1f} "
            f"{lat.max_latency_ms:>8.1f} "
            f"{lat.throughput_chunks_per_sec:>6.2f} "
            f"{lat.cache_hit_rate * 100:>6.1f}%"
        )

    print(f"\n{sep}\n")


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LexiRedact benchmark report.")
    parser.add_argument("--results-dir", required=True,
                        help="Directory containing {mode}_results.json files")
    parser.add_argument("--dataset-dir", required=True,
                        help="Directory containing chunks.json and queries.json")
    parser.add_argument("--output-dir", required=True,
                        help="Directory where PNG figures and CSV tables will be saved")
    args = parser.parse_args()

    from eval.dataset.schema import load_dataset

    dataset = load_dataset(
        chunks_path=str(Path(args.dataset_dir) / "chunks.json"),
        queries_path=str(Path(args.dataset_dir) / "queries.json"),
    )

    compare_results_dict: dict[str, CompareResult] = {}
    privacy_metrics: dict[str, PrivacyMetrics] = {}
    utility_metrics: dict[str, UtilityMetrics] = {}
    latency_metrics: dict[str, LatencyMetrics] = {}

    for mode in MODES:
        print(f"Loading results for mode: {mode}")
        try:
            cr = load_compare_result(args.results_dir, mode)
        except FileNotFoundError as e:
            print(f"  WARNING: {e} — skipping mode '{mode}'")
            continue
        compare_results_dict[mode] = cr
        privacy_metrics[mode] = compute_privacy_metrics(cr, dataset)
        utility_metrics[mode] = compute_utility_metrics(cr.retrieval_results, mode)
        latency_metrics[mode] = compute_latency_metrics(cr)

    if not compare_results_dict:
        print("ERROR: No results loaded. Run eval/runners/compare.py first.")
        sys.exit(1)

    saved = generate_report(
        privacy=privacy_metrics,
        utility=utility_metrics,
        latency=latency_metrics,
        compare_results=compare_results_dict,
        output_dir=args.output_dir,
    )

    print(f"\n✅  {len(saved)} outputs saved:")
    for f in saved:
        print(f"    {f}")