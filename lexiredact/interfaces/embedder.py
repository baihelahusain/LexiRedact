"""
Abstract embedder interface for LexiRedact.

Embedders generate vector representations of text.
LexiRedact embeds the ORIGINAL text (before redaction) to preserve semantic meaning.
"""
from abc import ABC, abstractmethod
from typing import List


class Embedder(ABC):
    """Abstract interface for text embedding generation."""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Vector embedding as list of floats
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of vector embeddings
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of generated embeddings.
        
        Returns:
            Embedding vector dimension (e.g., 384, 768)
        """
        pass