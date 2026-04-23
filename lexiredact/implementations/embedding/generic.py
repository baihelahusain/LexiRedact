"""
Generic embedder wrapper for universal embedding model support.
"""
from typing import List, Callable, Optional
import asyncio
from ...interfaces import Embedder


class GenericEmbedder(Embedder):
    """
    Universal embedder that wraps ANY embedding function.
    
    Users can integrate OpenAI, Cohere, Sentence-Transformers, or any custom model.
    """
    
    def __init__(
        self,
        embed_func: Callable[[str], List[float]],
        embed_batch_func: Optional[Callable[[List[str]], List[List[float]]]] = None,
        dimension: Optional[int] = None,
        name: str = "custom"
    ):
        """
        Initialize generic embedder.
        
        Args:
            embed_func: Function(text: str) -> List[float]
            embed_batch_func: Optional Function(texts: List[str]) -> List[List[float]]
            dimension: Embedding dimension (auto-detected if None)
            name: Embedder name for logging
            
        Examples:
            # OpenAI
            >>> from openai import OpenAI
            >>> client = OpenAI(api_key="sk-...")
            >>> embedder = GenericEmbedder(
            ...     embed_func=lambda text: client.embeddings.create(
            ...         input=text, model="text-embedding-3-small"
            ...     ).data[0].embedding,
            ...     dimension=1536,
            ...     name="openai"
            ... )
            
            # Sentence Transformers
            >>> from sentence_transformers import SentenceTransformer
            >>> model = SentenceTransformer('all-MiniLM-L6-v2')
            >>> embedder = GenericEmbedder(
            ...     embed_func=lambda text: model.encode(text).tolist(),
            ...     embed_batch_func=lambda texts: [e.tolist() for e in model.encode(texts)],
            ...     dimension=384,
            ...     name="sentence-transformers"
            ... )
            
            # Cohere
            >>> import cohere
            >>> co = cohere.Client(api_key="...")
            >>> embedder = GenericEmbedder(
            ...     embed_func=lambda text: co.embed(texts=[text]).embeddings[0],
            ...     embed_batch_func=lambda texts: co.embed(texts=texts).embeddings,
            ...     dimension=1024,
            ...     name="cohere"
            ... )
        """
        self.embed_func = embed_func
        self.embed_batch_func = embed_batch_func or self._default_batch
        self._dimension = dimension
        self.name = name
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        loop = asyncio.get_event_loop()
        
        # Support both sync and async functions
        result = self.embed_func(text)
        if hasattr(result, '__await__'):
            return await result
        else:
            # Run in executor to avoid blocking
            return await loop.run_in_executor(None, lambda: result)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        loop = asyncio.get_event_loop()
        
        result = self.embed_batch_func(texts)
        if hasattr(result, '__await__'):
            return await result
        else:
            return await loop.run_in_executor(None, lambda: result)
    
    def _default_batch(self, texts: List[str]) -> List[List[float]]:
        """Default batch: call embed_func for each text."""
        return [self.embed_func(text) for text in texts]
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            # Auto-detect by generating sample embedding
            sample = self.embed_func("test")
            self._dimension = len(sample)
        return self._dimension