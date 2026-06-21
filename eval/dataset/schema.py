"""
eval/dataset/schema.py — Dataset dataclasses and JSON loader for Lexiredact evaluation.

All evaluation modules share these types as their common currency. The schema is
intentionally minimal: it carries raw text + ground-truth annotations, not pipeline
outputs. Pipeline outputs (ProcessingResult) are separate and produced by compare.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnnotatedEntity:
    """A ground-truth PII annotation in a chunk's raw text.

    Attributes:
        text:        The exact PII substring as it appears in ``raw_text``.
        entity_type: Presidio entity label, e.g. ``"PERSON"``, ``"EMAIL_ADDRESS"``.
        start:       Start character offset (inclusive) in ``raw_text``.
        end:         End character offset (exclusive) in ``raw_text``.
    """

    text: str
    entity_type: str
    start: int
    end: int


@dataclass
class EvalChunk:
    """A single annotated text chunk for evaluation.

    Attributes:
        chunk_id:           Unique identifier. Used as the vector DB primary key.
        raw_text:           Original text with PII present. Never sanitized here.
        annotated_entities: Ground-truth PII spans. Used for privacy metric computation.
        topic_cluster:      Semantic grouping label (e.g. ``"billing_dispute"``).
    """

    chunk_id: str
    raw_text: str
    annotated_entities: list[AnnotatedEntity]
    topic_cluster: str


@dataclass
class EvalQuery:
    """A retrieval query with ground-truth relevant chunk IDs.

    Attributes:
        query_id:            Unique identifier for this query.
        query_text:          The query string. Paraphrased from chunks to test
                             semantic retrieval, not keyword matching.
        relevant_chunk_ids:  Ground-truth answer set. Hit@K counts a hit if ANY
                             of these appears in the top-K retrieved results.
        topic_cluster:       Same taxonomy as :class:`EvalChunk`.
    """

    query_id: str
    query_text: str
    relevant_chunk_ids: list[str]
    topic_cluster: str


@dataclass
class EvalDataset:
    """Container for the full evaluation dataset.

    Attributes:
        chunks:  All annotated chunks available for ingestion.
        queries: All queries with ground-truth relevant chunk IDs.
    """

    chunks: list[EvalChunk]
    queries: list[EvalQuery]

    def get_chunk(self, chunk_id: str) -> EvalChunk | None:
        """Return the chunk with the given ID, or None if not found."""
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def chunks_by_cluster(self, cluster: str) -> list[EvalChunk]:
        """Return all chunks belonging to the given topic cluster."""
        return [c for c in self.chunks if c.topic_cluster == cluster]

    def queries_by_cluster(self, cluster: str) -> list[EvalQuery]:
        """Return all queries belonging to the given topic cluster."""
        return [q for q in self.queries if q.topic_cluster == cluster]


# ── JSON loader ───────────────────────────────────────────────────────────────

def load_dataset(chunks_path: str, queries_path: str) -> EvalDataset:
    """Load an :class:`EvalDataset` from two JSON files.

    Args:
        chunks_path:  Path to ``chunks.json`` — a JSON array of chunk objects.
        queries_path: Path to ``queries.json`` — a JSON array of query objects.

    Returns:
        A fully populated :class:`EvalDataset`.

    Raises:
        ValueError: If either file is missing, cannot be parsed, or has wrong structure.
    """
    chunks = _load_chunks(chunks_path)
    queries = _load_queries(queries_path)
    return EvalDataset(chunks=chunks, queries=queries)


def _load_json_list(path: str, label: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"{label} file not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse {label} JSON at {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(
            f"{label} file must contain a JSON array, got {type(data).__name__}: {path}"
        )
    return data


def _load_chunks(path: str) -> list[EvalChunk]:
    raw_list = _load_json_list(path, "chunks")
    chunks: list[EvalChunk] = []
    for i, raw in enumerate(raw_list):
        try:
            entities = [
                AnnotatedEntity(
                    text=e["text"],
                    entity_type=e["entity_type"],
                    start=e["start"],
                    end=e["end"],
                )
                for e in raw.get("annotated_entities", [])
            ]
            chunks.append(
                EvalChunk(
                    chunk_id=raw["chunk_id"],
                    raw_text=raw["raw_text"],
                    annotated_entities=entities,
                    topic_cluster=raw["topic_cluster"],
                )
            )
        except KeyError as exc:
            raise ValueError(
                f"Chunk at index {i} is missing required field: {exc}"
            ) from exc
    return chunks


def _load_queries(path: str) -> list[EvalQuery]:
    raw_list = _load_json_list(path, "queries")
    queries: list[EvalQuery] = []
    for i, raw in enumerate(raw_list):
        try:
            queries.append(
                EvalQuery(
                    query_id=raw["query_id"],
                    query_text=raw["query_text"],
                    relevant_chunk_ids=raw["relevant_chunk_ids"],
                    topic_cluster=raw["topic_cluster"],
                )
            )
        except KeyError as exc:
            raise ValueError(
                f"Query at index {i} is missing required field: {exc}"
            ) from exc
    return queries
