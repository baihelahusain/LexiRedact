"""
Generic vector store wrapper for universal vector database support.
"""
from typing import List, Dict, Any, Optional, Callable
import asyncio
from ...interfaces import VectorStore


class GenericVectorStore(VectorStore):
    """
    Universal vector store that wraps ANY vector database.
    
    Users can integrate Pinecone, Weaviate, Qdrant, Milvus, or custom stores.
    """
    
    def __init__(
        self,
        add_func: Callable[[List[str], List[List[float]], List[str], Optional[List[Dict]]], None],
        query_func: Callable[[List[float], int, Optional[Dict]], List[Dict[str, Any]]],
        connect_func: Optional[Callable[[], None]] = None,
        close_func: Optional[Callable[[], None]] = None,
        delete_func: Optional[Callable[[List[str]], None]] = None,
        name: str = "custom"
    ):
        """
        Initialize generic vector store.
        
        Args:
            add_func: Function(ids, embeddings, documents, metadata) -> None
            query_func: Function(query_embedding, top_k, filters) -> List[Dict]
            connect_func: Optional connection function
            close_func: Optional cleanup function
            delete_func: Optional delete function
            name: Store name for logging
            
        Examples:
            # Pinecone
            >>> import pinecone
            >>> pinecone.init(api_key="...")
            >>> index = pinecone.Index("my-index")
            >>> store = GenericVectorStore(
            ...     add_func=lambda ids, embs, docs, meta: index.upsert(
            ...         vectors=[(id, emb, {"text": doc, **(m or {})}) 
            ...                  for id, emb, doc, m in zip(ids, embs, docs, meta or [{}]*len(ids))]
            ...     ),
            ...     query_func=lambda emb, k, filters: [
            ...         {"id": m["id"], "document": m["metadata"]["text"], 
            ...          "score": m["score"], "metadata": m["metadata"]}
            ...         for m in index.query(vector=emb, top_k=k, filter=filters).matches
            ...     ],
            ...     name="pinecone"
            ... )
            
            # Weaviate
            >>> import weaviate
            >>> client = weaviate.Client("http://localhost:8080")
            >>> store = GenericVectorStore(
            ...     add_func=lambda ids, embs, docs, meta: client.batch.add_data_object(...),
            ...     query_func=lambda emb, k, filters: client.query.get(...).with_near_vector(...).do(),
            ...     name="weaviate"
            ... )
        """
        self.add_func = add_func
        self.query_func = query_func
        self.connect_func = connect_func
        self.close_func = close_func
        self.delete_func = delete_func or (lambda ids: None)
        self.name = name
    
    async def connect(self) -> None:
        """Establish connection."""
        if self.connect_func:
            result = self.connect_func()
            if hasattr(result, '__await__'):
                await result
    
    async def close(self) -> None:
        """Close connection."""
        if self.close_func:
            result = self.close_func()
            if hasattr(result, '__await__'):
                await result
    
    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add vectors to store."""
        loop = asyncio.get_event_loop()
        result = self.add_func(ids, embeddings, documents, metadata)
        if hasattr(result, '__await__'):
            await result
        else:
            await loop.run_in_executor(None, lambda: result)
    
    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query for similar vectors."""
        loop = asyncio.get_event_loop()
        result = self.query_func(query_embedding, top_k, filter_metadata)
        if hasattr(result, '__await__'):
            return await result
        else:
            return await loop.run_in_executor(None, lambda: result)
    
    async def delete(self, ids: List[str]) -> None:
        """Delete vectors."""
        loop = asyncio.get_event_loop()
        result = self.delete_func(ids)
        if hasattr(result, '__await__'):
            await result
        else:
            await loop.run_in_executor(None, lambda: result)