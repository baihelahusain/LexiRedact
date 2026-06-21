"""Use a custom embedder with LexiredactPipeline."""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401
from _embedding_reference import InMemoryVectorStore

from lexiredact import LexiredactPipeline, load_config
from lexiredact.pipeline.embedder.base import EmbedderBase


class LengthEmbedder(EmbedderBase):
    """Simple example embedder that returns three numeric text features."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._features(text) for text in texts]

    def query_embed(self, texts: list[str]) -> list[list[float]]:
        return [self._features(text) for text in texts]

    def get_dimension(self) -> int:
        return 3

    @staticmethod
    def _features(text: str) -> list[float]:
        words = text.split()
        return [float(len(text)), float(len(words)), float(text.count("@"))]


config = load_config(
    {
        "pipeline_mode": "raw",
        "embedder": {"dimension": 3, "document_prefix": "", "query_prefix": ""},
        "store": {"collection_name": "custom_embedder_demo"},
    }
)

store = InMemoryVectorStore()
pipeline = LexiredactPipeline(config, embedder=LengthEmbedder(), store=store)

results = pipeline.ingest(
    [
        {"id": "a", "text": "Short text."},
        {"id": "b", "text": "A longer document with an email jane@example.com."},
    ]
)

print([result.to_dict() for result in results])
print(store.records)
