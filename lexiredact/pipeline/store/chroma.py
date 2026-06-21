"""
pipeline/store/chroma.py — ChromaDB implementation of VectorStoreBase.

Uses persistent local storage (no server needed). Collection created on first use
with cosine similarity (hnsw:space: cosine).

Privacy: only SANITISED text is ever written to metadata. Original text is never stored.
"""

from __future__ import annotations

from typing import Any

from lexiredact.config.schema import StoreConfig
from lexiredact.exceptions import LexiredactStorageError
from lexiredact.app_logging import get_logger
from lexiredact.pipeline.store.base import VectorStoreBase

logger = get_logger(__name__)


class ChromaStore(VectorStoreBase):
    """ChromaDB vector store with persistent local storage and cosine similarity.

    Args:
        config:              Store configuration (collection_name, persist_directory).
        embedding_dimension: Embedder output dimension (stored for reference).
    """

    def __init__(self, config: StoreConfig, embedding_dimension: int) -> None:
        self._config = config
        self._embedding_dimension = embedding_dimension
        try:
            import chromadb  # type: ignore[import-untyped]
            self._client = chromadb.PersistentClient(path=config.persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=config.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaStore connected: collection=%s persist_dir=%s dim=%d",
                config.collection_name, config.persist_directory, embedding_dimension,
            )
        except Exception as exc:
            raise LexiredactStorageError(
                f"Failed to initialise ChromaDB: {exc}",
                context={
                    "collection": config.collection_name,
                    "persist_directory": config.persist_directory,
                },
            ) from exc

    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Write chunks to ChromaDB. Existing ids are overwritten (upsert semantics).

        Raises:
            LexiredactStorageError: Wraps any ChromaDB exception.
        """
        try:
            self._collection.upsert(ids=ids, embeddings=vectors, metadatas=metadatas)
            logger.debug("Upserted %d chunks to collection '%s'.",
                         len(ids), self._config.collection_name)
        except Exception as exc:
            raise LexiredactStorageError(
                f"ChromaDB upsert failed: {exc}",
                context={"collection": self._config.collection_name, "batch_size": len(ids)},
            ) from exc

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query ChromaDB for top_k nearest neighbours.

        Returns:
            List of {"id": str, "metadata": dict, "distance": float}, most similar first.

        Raises:
            LexiredactStorageError: Wraps any ChromaDB exception.
        """
        try:
            kwargs: dict[str, Any] = {
                "query_embeddings": [query_vector],
                "n_results": top_k,
                "include": ["metadatas", "distances"],
            }
            if filters is not None:
                kwargs["where"] = filters
            raw = self._collection.query(**kwargs)
            ids: list[str] = raw["ids"][0]
            metas: list[dict[str, Any]] = raw["metadatas"][0]
            dists: list[float] = raw["distances"][0]
            return [
                {"id": id_, "metadata": meta, "distance": dist}
                for id_, meta, dist in zip(ids, metas, dists)
            ]
        except Exception as exc:
            raise LexiredactStorageError(
                f"ChromaDB query failed: {exc}",
                context={"collection": self._config.collection_name, "top_k": top_k},
            ) from exc

    def count(self) -> int:
        """Return total stored document count.

        Raises:
            LexiredactStorageError: Wraps any ChromaDB exception.
        """
        try:
            return self._collection.count()
        except Exception as exc:
            raise LexiredactStorageError(
                f"ChromaDB count failed: {exc}",
                context={"collection": self._config.collection_name},
            ) from exc
