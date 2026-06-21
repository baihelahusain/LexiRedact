"""
eval/metrics/privacy.py — PII detection quality metrics.

Compares what Presidio detected (ProcessingResult.entities_detected) against
what ground truth says should have been found (EvalChunk.annotated_entities).

Matching rule for TRUE POSITIVES (recall direction):
  entity_type must match exactly AND character span overlap must exceed 50%
  of the ground-truth span length. This handles Presidio's tendency to return
  slightly different boundaries than human annotators.

Matching rule for FALSE POSITIVES (precision direction):
  A detected entity is a true positive if it matches ANY ground-truth span
  with >50% overlap of the detection span length AND matching entity_type.
  If no such match exists, the detection is a false positive.

mode="raw" always yields recall=0.0, precision=0.0, f1=0.0 because no
detection runs in raw mode. This is intentional and correct — it is the
privacy floor of the baseline.

Entity type alignment note:
  The eval dataset contains IP_ADDRESS annotations (IT security chunks).
  For privacy metrics to be correct, the config must include IP_ADDRESS
  in its entities list. If it does not, all IP_ADDRESS spans will appear
  as false negatives (fnr_by_entity_type["IP_ADDRESS"] = 1.0), which
  misrepresents the detector's capability rather than the pipeline's privacy.
  The lexiredact_config.yaml and PIIConfig defaults now include IP_ADDRESS.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.dataset.schema import AnnotatedEntity, EvalDataset
from eval.runners.compare import CompareResult
from lexiredact.models.result import DetectedEntity


@dataclass
class PrivacyMetrics:
    """Aggregated PII detection quality metrics for one pipeline mode.

    Attributes:
        mode:               Pipeline mode label.
        pii_recall:         Fraction of annotated entities that were detected.
                            ``= total_detected_correctly / total_annotated``
        pii_precision:      Of all entities Presidio detected, the fraction that
                            are genuine PII (matched to ground truth).
                            ``= total_true_positives / (total_true_positives + total_false_positives)``
                            0.0 for raw mode (no detection runs).
        pii_f1:             Harmonic mean of pii_precision and pii_recall.
                            0.0 for raw mode.
        false_negative_rate: Fraction of annotated entities that were MISSED.
                            ``= total_missed / total_annotated``
        false_positive_rate_of_detections: FP / (TP + FP) — fraction of all
                            detections that are spurious.
                            0.0 for raw mode.
        fnr_by_entity_type: FNR broken down per Presidio entity type.
                            Useful for identifying which types Presidio struggles with.
        precision_by_entity_type: Precision per entity type.
        f1_by_entity_type:  F1 per entity type.
        total_annotated:    Total ground-truth PII spans across all chunks.
        total_detected:     Total spans correctly detected (matched to ground truth).
        total_missed:       Total spans in ground truth that were not detected.
        total_false_positives: Detections that do not match any ground-truth span.
    """

    mode: str
    pii_recall: float
    pii_precision: float
    pii_f1: float
    false_negative_rate: float
    false_positive_rate_of_detections: float
    fnr_by_entity_type: dict[str, float]
    precision_by_entity_type: dict[str, float]
    f1_by_entity_type: dict[str, float]
    total_annotated: int
    total_detected: int
    total_missed: int
    total_false_positives: int


def compute_privacy_metrics(
    compare_result: CompareResult,
    dataset: EvalDataset,
) -> PrivacyMetrics:
    """Compute PII detection quality metrics for one pipeline mode.

    Iterates over every ingest result, looks up the corresponding ground-truth
    chunk, and matches detected entities to annotated entities using the 50%
    span-overlap rule for both recall (false negatives) and precision
    (false positives).

    For raw mode, all precision/recall/F1 values are 0.0 because no detection
    runs — this correctly represents the privacy cost of the raw baseline.

    Args:
        compare_result: Results from one pipeline mode run.
        dataset:        Eval dataset carrying ground-truth annotations.

    Returns:
        A :class:`PrivacyMetrics` instance for the given mode.
    """
    # Counters keyed by entity type.
    annotated_by_type: dict[str, int] = defaultdict(int)
    tp_by_type: dict[str, int] = defaultdict(int)       # true positives per type
    fp_by_type: dict[str, int] = defaultdict(int)       # false positives per type
    total_det_by_type: dict[str, int] = defaultdict(int) # all detections per type

    total_annotated = 0
    total_true_positives = 0
    total_false_positives = 0

    for ingest_result in compare_result.ingest_results:
        eval_chunk = dataset.get_chunk(ingest_result.chunk_id)
        if eval_chunk is None:
            # Warmup chunk or unknown chunk — skip silently.
            continue

        ground_truth = eval_chunk.annotated_entities
        detected = ingest_result.entities_detected

        # ── Recall direction: count false negatives ────────────────────────────
        for gt_entity in ground_truth:
            annotated_by_type[gt_entity.entity_type] += 1
            total_annotated += 1

            if _is_detected(gt_entity, detected):
                tp_by_type[gt_entity.entity_type] += 1
                total_true_positives += 1

        # ── Precision direction: count false positives ─────────────────────────
        for det_entity in detected:
            total_det_by_type[det_entity.entity_type] += 1
            if not _is_true_positive(det_entity, ground_truth):
                fp_by_type[det_entity.entity_type] += 1
                total_false_positives += 1

    total_missed = total_annotated - total_true_positives

    # ── Aggregate metrics ──────────────────────────────────────────────────────
    pii_recall = total_true_positives / total_annotated if total_annotated else 0.0
    fnr = total_missed / total_annotated if total_annotated else 1.0

    total_detections = total_true_positives + total_false_positives
    pii_precision = total_true_positives / total_detections if total_detections > 0 else 0.0
    fp_rate_of_detections = (
        total_false_positives / total_detections if total_detections > 0 else 0.0
    )

    # Harmonic mean (F1)
    pii_f1 = (
        2 * pii_precision * pii_recall / (pii_precision + pii_recall)
        if (pii_precision + pii_recall) > 0 else 0.0
    )

    # ── Per-entity-type breakdowns ─────────────────────────────────────────────
    all_types = set(annotated_by_type.keys()) | set(total_det_by_type.keys())

    fnr_by_type: dict[str, float] = {}
    precision_by_type: dict[str, float] = {}
    f1_by_type: dict[str, float] = {}

    for etype in all_types:
        ann = annotated_by_type.get(etype, 0)
        tp = tp_by_type.get(etype, 0)
        fp = fp_by_type.get(etype, 0)
        total_det = total_det_by_type.get(etype, 0)

        # FNR: missed / annotated
        if ann > 0:
            fnr_by_type[etype] = round((ann - tp) / ann, 4)
        else:
            fnr_by_type[etype] = 0.0  # Never annotated → no false negatives

        # Precision: TP / (TP + FP)
        if total_det > 0:
            precision_by_type[etype] = round(tp / total_det, 4)
        else:
            precision_by_type[etype] = 0.0  # Nothing detected

        # Recall for this type
        recall_type = tp / ann if ann > 0 else 0.0

        # F1 per type
        p_t = precision_by_type[etype]
        if (p_t + recall_type) > 0:
            f1_by_type[etype] = round(2 * p_t * recall_type / (p_t + recall_type), 4)
        else:
            f1_by_type[etype] = 0.0

    return PrivacyMetrics(
        mode=compare_result.mode,
        pii_recall=round(pii_recall, 4),
        pii_precision=round(pii_precision, 4),
        pii_f1=round(pii_f1, 4),
        false_negative_rate=round(fnr, 4),
        false_positive_rate_of_detections=round(fp_rate_of_detections, 4),
        fnr_by_entity_type=fnr_by_type,
        precision_by_entity_type=precision_by_type,
        f1_by_entity_type=f1_by_type,
        total_annotated=total_annotated,
        total_detected=total_true_positives,
        total_missed=total_missed,
        total_false_positives=total_false_positives,
    )


def _is_detected(
    ground_truth: AnnotatedEntity,
    detected: list[DetectedEntity],
) -> bool:
    """Return True if any detected entity matches the ground-truth span.

    Matching criteria:
      - ``entity_type`` must match exactly (case-sensitive).
      - Overlap of the detected span with the ground-truth span must exceed
        50% of the ground-truth span length.

    A lenient overlap threshold accommodates Presidio's tendency to return
    slightly wider or narrower boundaries than human annotators.

    Args:
        ground_truth: One annotated entity from EvalChunk.
        detected:     All entities detected by Presidio for that chunk.

    Returns:
        True if at least one detected entity satisfies both criteria.
    """
    gt_len = ground_truth.end - ground_truth.start
    if gt_len == 0:
        return False

    for det in detected:
        if det.entity_type != ground_truth.entity_type:
            continue
        # Compute character-level overlap.
        overlap_start = max(det.start, ground_truth.start)
        overlap_end = min(det.end, ground_truth.end)
        overlap = max(0, overlap_end - overlap_start)
        if overlap / gt_len > 0.5:
            return True
    return False


def _is_true_positive(
    detected: DetectedEntity,
    ground_truths: list[AnnotatedEntity],
) -> bool:
    """Return True if a detected entity matches any ground-truth span.

    This is the precision-direction complement of ``_is_detected()``.
    Matching criteria:
      - ``entity_type`` must match exactly.
      - Overlap of the detection span with the ground-truth span must exceed
        50% of the DETECTION span length (not the ground-truth span length,
        because we are evaluating whether this detection is legitimate).

    Args:
        detected:      A single detected entity from Presidio.
        ground_truths: All ground-truth annotations for this chunk.

    Returns:
        True if the detection corresponds to a real PII span in the ground truth.
    """
    det_len = detected.end - detected.start
    if det_len == 0:
        return False

    for gt in ground_truths:
        if gt.entity_type != detected.entity_type:
            continue
        overlap_start = max(detected.start, gt.start)
        overlap_end = min(detected.end, gt.end)
        overlap = max(0, overlap_end - overlap_start)
        if overlap / det_len > 0.5:
            return True
    return False