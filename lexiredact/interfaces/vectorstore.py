"""
Abstract vector store interface for LexiRedact.

Vector stores persist embeddings and sanitized text.
Only clean text (with PII redacted) should be stored.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorStore(ABC):
    """Abstract interface for vector database operations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to vector database."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connection and cleanup resources."""
        pass
    
    @abstractmethod
    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add vectors to the database.
        
        Args:
            ids: Document IDs
            embeddings: Vector embeddings
            documents: Text documents (must be sanitized/redacted)
            metadata: Optional metadata for each document
        """
        pass
    
    @abstractmethod
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
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of results with 'id', 'document', 'score', 'metadata'
        """
        pass
    
    @abstractmethod
    async def delete(self, ids: List[str]) -> None:
        """
        Delete vectors by ID.
        
        Args:
            ids: Document IDs to delete
        """
        pass

    async def peek(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return a small sample of stored records when supported.

        Concrete backends may override this for inspection/debugging.
        """
        raise NotImplementedError("This vector store does not support peek().")

    def get_collection_info(self) -> Dict[str, Any]:
        """
        Return collection/storage metadata when supported.

        Concrete backends may override this for inspection/debugging.
        """
        raise NotImplementedError(
            "This vector store does not support get_collection_info()."
        )
