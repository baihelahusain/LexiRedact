"""
eval/metrics/utility.py — Retrieval quality metrics (Hit@K, Recall@K, nDCG@K, MRR).

Hit@K: A query counts as a "hit" at rank K if ANY of its relevant chunk IDs
appears in the top-K retrieved results. Does NOT require ALL relevant chunks.

Recall@K: Fraction of ALL relevant chunks found in the top K retrieved results.
  Formula: |retrieved_top_K ∩ relevant| / |relevant|
  With 4–6 relevant chunks per query, this metric exposes quality differences
  that Hit@K cannot — returning 1/6 vs 5/6 both give Hit@K=1 but very
  different Recall@K values.

nDCG@K (Normalized Discounted Cumulative Gain): The gold-standard ranked
  retrieval metric. Rewards finding MORE relevant items at HIGHER ranks.
  Relevance is binary (1 if in relevant set, 0 otherwise).
  DCG@K  = Σ_{i=1}^{K} rel_i / log2(i+1)
  IDCG@K = ideal DCG (all relevant items ranked first)
  nDCG@K = DCG@K / IDCG@K  ∈ [0, 1]

MRR (Mean Reciprocal Rank): 1/rank of the FIRST relevant chunk found in the
retrieved list. 0.0 if no relevant chunk appears in the retrieved results.
Averaged across all queries.

These metrics together reveal the utility gap caused by PII redaction:
  - raw:         highest Hit@K, Recall@K, nDCG@K, and MRR (original text embedding)
  - preredacted: lower scores (semantic embedding from sanitized text)
  - dual:        should match raw (embedding from original, storage sanitized)

The primary claim of the Lexiredact paper — that dual mode maintains retrieval
quality equal to raw while adding privacy — is best validated by comparing
nDCG@5 across modes: if dual ≈ raw >> preredacted, the claim is substantiated.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.runners.compare import RetrievalResult


@dataclass
class UtilityMetrics:
    """Retrieval quality metrics for one pipeline mode.

    Attributes:
        mode:          Pipeline mode label.
        hit_at_1:      Fraction of queries where a relevant chunk is rank 1.
        hit_at_3:      Fraction of queries where a relevant chunk is in top 3.
        hit_at_5:      Fraction of queries where a relevant chunk is in top 5.
        recall_at_3:   Mean fraction of relevant chunks found in top 3.
        recall_at_5:   Mean fraction of relevant chunks found in top 5.
        ndcg_at_3:     Mean nDCG at rank 3.
        ndcg_at_5:     Mean nDCG at rank 5.
        mrr:           Mean Reciprocal Rank across all queries.
        total_queries: Number of queries evaluated.
    """

    mode: str
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    recall_at_3: float
    recall_at_5: float
    ndcg_at_3: float
    ndcg_at_5: float
    mrr: float
    total_queries: int


def _compute_ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at rank K.

    Relevance is binary: 1 if the chunk is in the relevant set, 0 otherwise.
    IDCG is computed assuming the ideal ranking places all relevant items first.

    Args:
        retrieved: Ordered list of retrieved chunk IDs (most similar first).
        relevant:  Set of ground-truth relevant chunk IDs for this query.
        k:         Cutoff rank.

    Returns:
        nDCG@K ∈ [0, 1]. Returns 0.0 if relevant is empty or idcg is 0.
    """
    if not relevant:
        return 0.0

    # DCG: sum of 1/log2(rank+1) for each relevant item in top K
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, cid in enumerate(retrieved[:k], start=1)
        if cid in relevant
    )

    # IDCG: ideal DCG — all min(|relevant|, k) relevant items ranked first
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))

    return dcg / idcg if idcg > 0 else 0.0


def _compute_recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant chunks that appear in the top K retrieved results.

    Formula: |retrieved_top_K ∩ relevant| / |relevant|

    Args:
        retrieved: Ordered list of retrieved chunk IDs.
        relevant:  Set of ground-truth relevant chunk IDs.
        k:         Cutoff rank.

    Returns:
        Recall@K ∈ [0, 1]. Returns 0.0 if relevant is empty.
    """
    if not relevant:
        return 0.0
    found = sum(1 for cid in retrieved[:k] if cid in relevant)
    return found / len(relevant)


def compute_utility_metrics(
    retrieval_results: list[RetrievalResult],
    mode: str = "",
) -> UtilityMetrics:
    """Compute Hit@K, Recall@K, nDCG@K, and MRR from a list of retrieval results.

    Hit@K logic: a query "hits" at K if ANY relevant chunk ID appears in the
    first K retrieved chunk IDs. Multiple relevant chunks do not give extra
    credit — one match is sufficient. Kept for backward compatibility with
    standard RAG benchmark reporting (DPR, REALM, FiD papers).

    Recall@K logic: compute per-query fraction of relevant chunks found in
    top K, then average across all queries. This metric is critical for
    datasets with multiple relevant chunks per query.

    nDCG@K logic: compute per-query nDCG then average across all queries.

    MRR logic: find the rank (1-indexed) of the FIRST relevant chunk in the
    retrieved list. Reciprocal = 1/rank. If none found, reciprocal = 0.
    MRR = mean across all queries.

    Args:
        retrieval_results: One :class:`RetrievalResult` per query.
        mode:              Mode label to embed in the returned metrics object.

    Returns:
        A :class:`UtilityMetrics` instance with all metrics computed.
    """
    if not retrieval_results:
        return UtilityMetrics(
            mode=mode,
            hit_at_1=0.0, hit_at_3=0.0, hit_at_5=0.0,
            recall_at_3=0.0, recall_at_5=0.0,
            ndcg_at_3=0.0, ndcg_at_5=0.0,
            mrr=0.0, total_queries=0,
        )

    n = len(retrieval_results)
    hits_1 = hits_3 = hits_5 = 0
    recall_3_sum = recall_5_sum = 0.0
    ndcg_3_sum = ndcg_5_sum = 0.0
    reciprocal_ranks: list[float] = []

    for rr in retrieval_results:
        relevant = set(rr.relevant_chunk_ids)
        retrieved = rr.retrieved_chunk_ids  # ordered by similarity

        # Hit@K checks — ANY relevant chunk in top K (binary, 1 match = full credit).
        if any(cid in relevant for cid in retrieved[:1]):
            hits_1 += 1
        if any(cid in relevant for cid in retrieved[:3]):
            hits_3 += 1
        if any(cid in relevant for cid in retrieved[:5]):
            hits_5 += 1

        # Recall@K — fraction of ALL relevant chunks found in top K.
        recall_3_sum += _compute_recall_at_k(retrieved, relevant, k=3)
        recall_5_sum += _compute_recall_at_k(retrieved, relevant, k=5)

        # nDCG@K — normalized discounted cumulative gain at rank K.
        ndcg_3_sum += _compute_ndcg_at_k(retrieved, relevant, k=3)
        ndcg_5_sum += _compute_ndcg_at_k(retrieved, relevant, k=5)

        # MRR — rank of first relevant chunk (1-indexed).
        rr_score = 0.0
        for rank, cid in enumerate(retrieved, start=1):
            if cid in relevant:
                rr_score = 1.0 / rank
                break
        reciprocal_ranks.append(rr_score)

    mrr = sum(reciprocal_ranks) / n

    return UtilityMetrics(
        mode=mode,
        hit_at_1=round(hits_1 / n, 4),
        hit_at_3=round(hits_3 / n, 4),
        hit_at_5=round(hits_5 / n, 4),
        recall_at_3=round(recall_3_sum / n, 4),
        recall_at_5=round(recall_5_sum / n, 4),
        ndcg_at_3=round(ndcg_3_sum / n, 4),
        ndcg_at_5=round(ndcg_5_sum / n, 4),
        mrr=round(mrr, 4),
        total_queries=n,
    )