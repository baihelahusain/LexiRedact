"""
FastEmbed-based embedding implementation for VectorShield.

Default embedder using BAAI/bge-small-en-v1.5 model.
CPU-friendly and efficient for most use cases.
"""
from typing import List, Optional
import asyncio
from fastembed import TextEmbedding
from ...interfaces import Embedder


class FastEmbedEmbedder(Embedder):
    """
    Text embedding using FastEmbed library.
    
    Default model: BAAI/bge-small-en-v1.5 (384 dimensions)
    - Fast inference on CPU
    - Good balance of speed and quality
    - Small memory footprint
    """
    
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        """
        Initialize FastEmbed model.
        
        Args:
            model_name: FastEmbed model identifier
            
        Available models:
            - BAAI/bge-small-en-v1.5 (384 dim, recommended)
            - BAAI/bge-base-en-v1.5 (768 dim)
            - sentence-transformers/all-MiniLM-L6-v2 (384 dim)
        """
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name)
        self._dimension: Optional[int] = None
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Vector embedding as list of floats
        """
        loop = asyncio.get_event_loop()
        
        # Run in thread pool to avoid blocking event loop
        embedding = await loop.run_in_executor(
            None,
            lambda: list(self.model.embed([text]))[0]
        )
        
        return embedding.tolist()
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        This is more efficient than calling embed_text multiple times
        as it processes texts in parallel internally.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of vector embeddings
        """
        if not texts:
            return []
        
        loop = asyncio.get_event_loop()
        
        # FastEmbed handles batching internally
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self.model.embed(texts))
        )
        
        return [emb.tolist() for emb in embeddings]
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension (e.g., 384 for bge-small)
        """
        if self._dimension is None:
            # Generate a sample embedding to determine dimension
            sample = list(self.model.embed(["test"]))[0]
            self._dimension = len(sample)
        
        return self._dimension