"""Shared helpers for custom embedding examples."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Sequence

import lexiredact as vs

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)


@dataclass(frozen=True)
class EmbeddingModelOption:
    """Configuration for one embedding model example."""

    label: str
    model_name: str
    document_prefix: str = ""
    query_prefix: str = ""


@dataclass(frozen=True)
class RetrievalCase:
    """Query and expected document pair for retrieval checks."""

    query: str
    relevant_doc_id: str


DOCUMENTS: Sequence[vs.Document] = (
    vs.Document(
        id="security-1",
        text=(
            "The security policy requires multi-factor authentication, least "
            "privilege access, audit logs, and quarterly access reviews."
        ),
        metadata={"domain": "security"},
    ),
    vs.Document(
        id="billing-1",
        text=(
            "The billing workflow explains invoice creation, failed payment "
            "retries, refund approvals, and subscription renewal notices."
        ),
        metadata={"domain": "billing"},
    ),
    vs.Document(
        id="support-1",
        text=(
            "The support playbook defines severity levels, escalation paths, "
            "ticket ownership, customer updates, and response targets."
        ),
        metadata={"domain": "support"},
    ),
    vs.Document(
        id="hr-1",
        text=(
            "The onboarding handbook covers offer letters, background checks, "
            "equipment requests, payroll setup, and new hire orientation."
        ),
        metadata={"domain": "hr"},
    ),
)


QUERIES: Sequence[RetrievalCase] = (
    RetrievalCase(
        query="How do we enforce multi-factor authentication and access reviews?",
        relevant_doc_id="security-1",
    ),
    RetrievalCase(
        query="What happens when a subscription payment fails?",
        relevant_doc_id="billing-1",
    ),
    RetrievalCase(
        query="Where are customer ticket escalation rules defined?",
        relevant_doc_id="support-1",
    ),
    RetrievalCase(
        query="What do we do when preparing a new employee?",
        relevant_doc_id="hr-1",
    ),
)


class SentenceTransformerLexiRedactEmbedder(vs.Embedder):
    """SentenceTransformers adapter that satisfies LexiRedact's Embedder interface."""

    def __init__(
        self,
        model_name: str,
        document_prefix: str = "",
        query_prefix: str = "",
        local_files_only: bool = True,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "This example requires sentence-transformers. "
                "Install it with: pip install sentence-transformers"
            ) from exc

        self.model_name = model_name
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self.model = SentenceTransformer(
            model_name,
            local_files_only=local_files_only,
            token=False,
        )
        dimension = self.model.get_sentence_embedding_dimension()
        self.dimension = dimension or len(self.model.encode("dimension check"))

    async def embed_text(self, text: str) -> List[float]:
        """Embed one document for ingestion."""
        return await self._encode_one(f"{self.document_prefix}{text}")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents for ingestion."""
        prefixed_texts = [f"{self.document_prefix}{text}" for text in texts]
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, self.model.encode, prefixed_texts)
        return embeddings.tolist()

    async def embed_query(self, query: str) -> List[float]:
        """Embed a retrieval query using the model-specific query prefix."""
        return await self._encode_one(f"{self.query_prefix}{query}")

    def get_embedding_dimension(self) -> int:
        """Return embedding vector size."""
        return int(self.dimension)

    async def _encode_one(self, text: str) -> List[float]:
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, self.model.encode, text)
        return embedding.tolist()


async def evaluate_embedder_retrieval(
    pipeline: vs.IngestionPipeline,
    embedder: SentenceTransformerLexiRedactEmbedder,
    top_k: int = 3,
) -> Dict[str, float]:
    """Compute simple retrieval metrics for a custom embedder example."""
    evaluation_rows = []

    for item in QUERIES:
        query_embedding = await embedder.embed_query(item.query)
        results = await pipeline.vectorstore.query(query_embedding=query_embedding, top_k=top_k)
        retrieved_ids = [result["id"] for result in results]
        evaluation_rows.append(
            {
                "query_id": item.query,
                "expected_ids": [item.relevant_doc_id],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = vs.RetrievalMetricsEvaluator.evaluate_queries(evaluation_rows, k=top_k)
    summary = metrics["summary"]
    recall_at_1 = (
        sum(
            1
            for row in evaluation_rows
            if row["retrieved_ids"] and row["retrieved_ids"][0] in row["expected_ids"]
        )
        / len(evaluation_rows)
        if evaluation_rows
        else 0.0
    )
    return {
        "recall_at_1": recall_at_1,
        "recall_at_k": summary["recall_at_k"],
        "mrr": summary["mean_reciprocal_rank"],
    }
