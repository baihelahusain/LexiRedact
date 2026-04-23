"""
Metrics and statistics collection for LexiRedact.

Tracks performance, privacy, operational, and optional retrieval metrics.
"""
from typing import Dict, Any, List, Sequence
from dataclasses import dataclass, field, asdict
import time
from threading import Lock


@dataclass
class IngestionMetrics:
    """Metrics for a single ingestion operation."""
    
    document_id: str
    status: str  # "success" or "failed"
    total_time_ms: float
    pii_detection_time_ms: float
    embedding_time_ms: float
    storage_time_ms: float
    pii_entities_found: List[str] = field(default_factory=list)
    cache_hit: bool = False
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AggregateStats:
    """Aggregate statistics across multiple operations."""
    
    total_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0
    
    total_pii_entities: int = 0
    unique_pii_types: set = field(default_factory=set)
    
    cache_hits: int = 0
    cache_misses: int = 0
    
    total_time_seconds: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    
    avg_pii_detection_ms: float = 0.0
    avg_embedding_ms: float = 0.0
    avg_storage_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['unique_pii_types'] = list(self.unique_pii_types)
        return data
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful_documents / self.total_documents if self.total_documents > 0 else 0.0
    
    @property
    def privacy_overhead_percent(self) -> float:
        """
        Calculate privacy overhead.
        
        Privacy overhead = (PII detection time) / (Total time) * 100
        This measures the percentage of time spent on privacy protection.
        """
        if self.avg_latency_ms == 0:
            return 0.0
        return (self.avg_pii_detection_ms / self.avg_latency_ms) * 100


@dataclass
class RetrievalQueryMetrics:
    """Metrics for a single retrieval query evaluation."""

    query_id: str
    expected_ids: List[str]
    retrieved_ids: List[str]
    top_k: int
    reciprocal_rank: float
    recall_at_k: float
    first_relevant_rank: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RetrievalAggregateStats:
    """Aggregate statistics across a retrieval evaluation set."""

    total_queries: int = 0
    queries_with_hits: int = 0
    mean_reciprocal_rank: float = 0.0
    recall_at_k: float = 0.0
    average_first_relevant_rank: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class RetrievalMetricsEvaluator:
    """
    Standalone retrieval evaluation helpers.

    These utilities are intentionally independent from the ingestion pipeline
    so LexiRedact stays focused on PII-safe processing while still exposing
    common retrieval-quality checks for users comparing embedding models.
    """

    @staticmethod
    def reciprocal_rank(
        expected_ids: Sequence[str],
        retrieved_ids: Sequence[str],
    ) -> float:
        """Compute reciprocal rank for one query."""
        expected = set(expected_ids)
        if not expected:
            return 0.0

        for index, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in expected:
                return 1.0 / index
        return 0.0

    @staticmethod
    def recall_at_k(
        expected_ids: Sequence[str],
        retrieved_ids: Sequence[str],
        k: int,
    ) -> float:
        """Compute recall@k for one query."""
        if k <= 0:
            raise ValueError("k must be greater than 0")

        expected = set(expected_ids)
        if not expected:
            return 0.0

        hits = expected.intersection(retrieved_ids[:k])
        return len(hits) / len(expected)

    @staticmethod
    def evaluate_query(
        query_id: str,
        expected_ids: Sequence[str],
        retrieved_ids: Sequence[str],
        k: int = 5,
    ) -> RetrievalQueryMetrics:
        """Evaluate one retrieval query."""
        if k <= 0:
            raise ValueError("k must be greater than 0")

        expected = list(expected_ids)
        retrieved = list(retrieved_ids)
        reciprocal_rank = RetrievalMetricsEvaluator.reciprocal_rank(expected, retrieved)
        recall_at_k = RetrievalMetricsEvaluator.recall_at_k(expected, retrieved, k)

        first_relevant_rank = None
        expected_lookup = set(expected)
        for index, doc_id in enumerate(retrieved, start=1):
            if doc_id in expected_lookup:
                first_relevant_rank = index
                break

        return RetrievalQueryMetrics(
            query_id=query_id,
            expected_ids=expected,
            retrieved_ids=retrieved,
            top_k=k,
            reciprocal_rank=reciprocal_rank,
            recall_at_k=recall_at_k,
            first_relevant_rank=first_relevant_rank,
        )

    @staticmethod
    def evaluate_queries(
        queries: Sequence[Dict[str, Any]],
        k: int = 5,
    ) -> Dict[str, Any]:
        """
        Evaluate multiple queries.

        Each query item must include:
        - `query_id`
        - `expected_ids`
        - `retrieved_ids`
        """
        if k <= 0:
            raise ValueError("k must be greater than 0")

        per_query: List[RetrievalQueryMetrics] = []
        first_ranks: List[int] = []

        for item in queries:
            metric = RetrievalMetricsEvaluator.evaluate_query(
                query_id=str(item["query_id"]),
                expected_ids=item["expected_ids"],
                retrieved_ids=item["retrieved_ids"],
                k=k,
            )
            per_query.append(metric)
            if metric.first_relevant_rank is not None:
                first_ranks.append(metric.first_relevant_rank)

        total_queries = len(per_query)
        queries_with_hits = sum(1 for item in per_query if item.first_relevant_rank is not None)
        mean_reciprocal_rank = (
            sum(item.reciprocal_rank for item in per_query) / total_queries
            if total_queries
            else 0.0
        )
        mean_recall_at_k = (
            sum(item.recall_at_k for item in per_query) / total_queries
            if total_queries
            else 0.0
        )
        average_first_relevant_rank = (
            sum(first_ranks) / len(first_ranks)
            if first_ranks
            else 0.0
        )

        summary = RetrievalAggregateStats(
            total_queries=total_queries,
            queries_with_hits=queries_with_hits,
            mean_reciprocal_rank=mean_reciprocal_rank,
            recall_at_k=mean_recall_at_k,
            average_first_relevant_rank=average_first_relevant_rank,
        )

        return {
            "summary": summary.to_dict(),
            "per_query": [item.to_dict() for item in per_query],
        }


class MetricsCollector:
    """
    Collects and aggregates LexiRedact metrics.
    
    Thread-safe metrics collection for concurrent operations.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: List[IngestionMetrics] = []
        self.stats = AggregateStats()
        self._lock = Lock()
    
    def record(self, metric: IngestionMetrics) -> None:
        """
        Record a single ingestion metric.
        
        Args:
            metric: Ingestion metrics to record
        """
        with self._lock:
            self.metrics.append(metric)
            self._update_stats(metric)
    
    def _update_stats(self, metric: IngestionMetrics) -> None:
        """Update aggregate statistics with new metric."""
        self.stats.total_documents += 1
        
        if metric.status == "success":
            self.stats.successful_documents += 1
        else:
            self.stats.failed_documents += 1
        
        # PII statistics
        self.stats.total_pii_entities += len(metric.pii_entities_found)
        self.stats.unique_pii_types.update(metric.pii_entities_found)
        
        # Cache statistics
        if metric.cache_hit:
            self.stats.cache_hits += 1
        else:
            self.stats.cache_misses += 1
        
        # Timing statistics
        self.stats.total_time_seconds += metric.total_time_ms / 1000
        
        # Update averages (incremental)
        n = self.stats.total_documents
        self.stats.avg_latency_ms = (
            (self.stats.avg_latency_ms * (n - 1) + metric.total_time_ms) / n
        )
        self.stats.avg_pii_detection_ms = (
            (self.stats.avg_pii_detection_ms * (n - 1) + metric.pii_detection_time_ms) / n
        )
        self.stats.avg_embedding_ms = (
            (self.stats.avg_embedding_ms * (n - 1) + metric.embedding_time_ms) / n
        )
        self.stats.avg_storage_ms = (
            (self.stats.avg_storage_ms * (n - 1) + metric.storage_time_ms) / n
        )
        
        # Min/Max latency
        self.stats.min_latency_ms = min(self.stats.min_latency_ms, metric.total_time_ms)
        self.stats.max_latency_ms = max(self.stats.max_latency_ms, metric.total_time_ms)
    
    def get_stats(self) -> AggregateStats:
        """
        Get current aggregate statistics.
        
        Returns:
            Copy of current statistics
        """
        with self._lock:
            # Return a copy to prevent modification
            import copy
            return copy.deepcopy(self.stats)
    
    def get_recent_metrics(self, n: int = 10) -> List[IngestionMetrics]:
        """
        Get the n most recent metrics.
        
        Args:
            n: Number of recent metrics to retrieve
            
        Returns:
            List of recent metrics
        """
        with self._lock:
            return self.metrics[-n:]
    
    def reset(self) -> None:
        """Reset all metrics and statistics."""
        with self._lock:
            self.metrics.clear()
            self.stats = AggregateStats()
    
    def export_summary(self) -> Dict[str, Any]:
        """
        Export a comprehensive summary for reporting.
        
        Returns:
            Dictionary with summary statistics
        """
        stats = self.get_stats()
        
        return {
            "overview": {
                "total_documents": stats.total_documents,
                "successful": stats.successful_documents,
                "failed": stats.failed_documents,
                "success_rate": f"{stats.success_rate * 100:.2f}%"
            },
            "privacy": {
                "total_pii_entities_redacted": stats.total_pii_entities,
                "unique_pii_types": list(stats.unique_pii_types),
                "avg_entities_per_doc": stats.total_pii_entities / stats.total_documents if stats.total_documents > 0 else 0
            },
            "performance": {
                "avg_latency_ms": f"{stats.avg_latency_ms:.2f}",
                "min_latency_ms": f"{stats.min_latency_ms:.2f}",
                "max_latency_ms": f"{stats.max_latency_ms:.2f}",
                "total_time_seconds": f"{stats.total_time_seconds:.2f}",
                "privacy_overhead_percent": f"{stats.privacy_overhead_percent:.2f}%"
            },
            "caching": {
                "cache_hits": stats.cache_hits,
                "cache_misses": stats.cache_misses,
                "cache_hit_rate": f"{stats.cache_hit_rate * 100:.2f}%"
            },
            "breakdown": {
                "avg_pii_detection_ms": f"{stats.avg_pii_detection_ms:.2f}",
                "avg_embedding_ms": f"{stats.avg_embedding_ms:.2f}",
                "avg_storage_ms": f"{stats.avg_storage_ms:.2f}"
            }
        }
