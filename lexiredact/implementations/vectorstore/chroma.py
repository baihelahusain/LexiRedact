"""
ChromaDB vector store implementation for LexiRedact.

Default vector database with persistent storage.
Requires: pip install chromadb
"""
from typing import List, Dict, Any, Optional
import json
import os
import time
from ...interfaces import VectorStore

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class ChromaVectorStore(VectorStore):
    """
    ChromaDB-based vector storage.

    Provides persistent storage with SQLite backend.
    Suitable for production deployments with moderate scale.
    """

    def __init__(
        self,
        persist_directory: str = "./lexiredact_data",
        collection_name: str = "documents",
        verbose: bool = True,
    ):
        """
        Initialize ChromaDB vector store.

        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the collection

        Raises:
            ImportError: If chromadb is not installed
        """
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "ChromaDB support requires the chromadb package. "
                "Install with: pip install chromadb"
            )

        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.verbose = verbose
        self.snapshot_path = os.path.join(
            self.persist_directory,
            f"{self.collection_name}_snapshot.jsonl"
        )
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None

    async def connect(self) -> None:
        """Initialize ChromaDB client and collection."""
        os.makedirs(self.persist_directory, exist_ok=True)

        # PersistentClient makes the on-disk store explicit.
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "LexiRedact protected documents"}
        )

        if self.verbose:
            print(f"ChromaDB connected at {self.persist_directory}")
            print(
                f"   Collection: {self.collection_name} "
                f"({self.collection.count()} documents)"
            )

    async def close(self) -> None:
        """Close ChromaDB connection."""
        self.client = None
        self.collection = None

    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add vectors to ChromaDB.

        Args:
            ids: Document IDs
            embeddings: Vector embeddings
            documents: Text documents (sanitized)
            metadata: Optional metadata dicts
        """
        if not self.collection:
            raise RuntimeError("ChromaDB not connected. Call connect() first.")

        if not ids:
            return

        normalized_metadata = self._normalize_metadata(ids, documents, metadata)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=normalized_metadata
        )
        self._append_snapshot(ids, documents, normalized_metadata)

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query for similar vectors.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            filter_metadata: Optional metadata filters

        Returns:
            List of results with id, document, score, metadata
        """
        if not self.collection:
            raise RuntimeError("ChromaDB not connected. Call connect() first.")

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata if filter_metadata else None
        )

        formatted = []
        result_count = len(results["ids"][0]) if results.get("ids") else 0
        for i in range(result_count):
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "score": results["distances"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })

        return formatted

    async def peek(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return a small sample of stored records for inspection."""
        if not self.collection:
            raise RuntimeError("ChromaDB not connected. Call connect() first.")

        results = self.collection.peek(limit=limit)
        rows: List[Dict[str, Any]] = []
        total = len(results.get("ids", []))

        for i in range(total):
            rows.append({
                "id": results["ids"][i],
                "document": results["documents"][i] if results.get("documents") else None,
                "metadata": results["metadatas"][i] if results.get("metadatas") else {},
            })

        return rows

    async def delete(self, ids: List[str]) -> None:
        """
        Delete vectors by ID.

        Args:
            ids: Document IDs to delete
        """
        if not self.collection:
            raise RuntimeError("ChromaDB not connected. Call connect() first.")

        if ids:
            self.collection.delete(ids=ids)

    def count(self) -> int:
        """
        Get number of documents in collection.

        Returns:
            Document count
        """
        if not self.collection:
            return 0
        return self.collection.count()

    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get collection information.

        Returns:
            Dict with collection name, count, metadata
        """
        if not self.collection:
            return {}

        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata,
            "persist_directory": self.persist_directory,
            "snapshot_path": self.snapshot_path,
        }

    def _normalize_metadata(
        self,
        ids: List[str],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Ensure each metadata row is non-empty and uses Chroma-supported values.
        """
        normalized: List[Dict[str, Any]] = []
        source_metadata = metadata or [{} for _ in ids]

        for doc_id, document, item in zip(ids, documents, source_metadata):
            raw = item if isinstance(item, dict) else {}
            clean: Dict[str, Any] = {}

            for key, value in raw.items():
                if value is None:
                    continue

                if isinstance(value, (str, int, float, bool)):
                    clean[str(key)] = value
                else:
                    clean[str(key)] = json.dumps(value, ensure_ascii=True, sort_keys=True)

            clean.setdefault("_vs_document_id", doc_id)
            clean.setdefault("_vs_document_length", len(document))
            clean.setdefault("_vs_sanitized", True)

            normalized.append(clean)

        return normalized

    def _append_snapshot(
        self,
        ids: List[str],
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> None:
        """
        Write sanitized storage snapshots to a JSONL file for evaluation/debugging.
        """
        os.makedirs(self.persist_directory, exist_ok=True)

        with open(self.snapshot_path, "a", encoding="utf-8") as handle:
            for doc_id, document, meta in zip(ids, documents, metadata):
                row = {
                    "id": doc_id,
                    "document": document,
                    "metadata": meta,
                    "collection": self.collection_name,
                    "stored_at": time.time(),
                }
                handle.write(json.dumps(row, ensure_ascii=True) + "\n")
