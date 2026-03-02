"""
ChromaDB vector store implementation for VectorShield.

Default vector database with persistent storage.
Requires: pip install chromadb
"""
from typing import List, Dict, Any, Optional
import os
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
        persist_directory: str = "./vectorshield_data",
        collection_name: str = "documents"
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
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None
    
    async def connect(self) -> None:
        """Initialize ChromaDB client and collection."""
        # Create persist directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Initialize client with persistent storage
        self.client = chromadb.Client(Settings(
            persist_directory=self.persist_directory,
            anonymized_telemetry=False
        ))
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "VectorShield protected documents"}
        )
        
        print(f"✅ ChromaDB connected at {self.persist_directory}")
        print(f"   Collection: {self.collection_name} ({self.collection.count()} documents)")
    
    async def close(self) -> None:
        """Close ChromaDB connection."""
        # ChromaDB auto-persists, no explicit close needed
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
        
        # Prepare metadata
        if metadata is None:
            metadata = [{} for _ in ids]
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )
    
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
        
        # Build where clause from filter
        where = filter_metadata if filter_metadata else None
        
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "score": results["distances"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })
        
        return formatted
    
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
            "metadata": self.collection.metadata
        }