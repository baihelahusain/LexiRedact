"""
Custom Embedder Example

Demonstrates how to use VectorShield with a custom embedding provider.
Shows the dependency injection pattern.
"""
import asyncio
from typing import List
import vectorshield as vs


class CustomEmbedder(vs.Embedder):
    """
    Example custom embedder implementation.
    
    In production, you might use:
    - OpenAI embeddings (text-embedding-3-small)
    - Cohere embeddings
    - Custom fine-tuned models
    - Any other embedding service
    """
    
    def __init__(self, model_name: str = "custom-model"):
        """Initialize custom embedder."""
        self.model_name = model_name
        self.dimension = 768  # Example dimension
        print(f"🔧 Initialized custom embedder: {model_name}")
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        This is a mock implementation. In production, replace with
        actual API calls to your embedding service.
        """
        # Mock: Generate random embedding (replace with real logic)
        import hashlib
        import struct
        
        # Deterministic "embedding" based on text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        embedding = []
        
        for i in range(self.dimension):
            # Use hash bytes to generate pseudo-random floats
            idx = (i * 4) % len(hash_bytes)
            value = struct.unpack('f', hash_bytes[idx:idx+4])[0] if idx + 4 <= len(hash_bytes) else 0.0
            embedding.append(value)
        
        return embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        # Process in parallel
        tasks = [self.embed_text(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension


async def main():
    """Custom embedder example."""
    
    print("=" * 60)
    print("VectorShield - Custom Embedder Example")
    print("=" * 60)
    print()
    
    # Create custom embedder instance
    custom_embedder = CustomEmbedder(model_name="my-custom-model-v1")
    
    # Create pipeline with custom embedder
    # All other components use defaults
    print("Creating pipeline with custom embedder...")
    pipeline = vs.IngestionPipeline(embedder=custom_embedder)
    
    await pipeline.initialize()
    print()
    
    # Process sample document
    doc = vs.Document(
        id="custom_doc_1",
        text="This document uses a custom embedding model for vector generation",
        metadata={"embedder": "custom"}
    )
    
    print("Processing document with custom embedder...")
    result = await pipeline.process_document(doc)
    
    print(f"\n📄 Result:")
    print(f"   Document ID: {result.id}")
    print(f"   Clean Text: {result.clean_text}")
    print(f"   Embedding Dimension: {len(result.embedding_preview) if result.status == 'success' else 'N/A'}")
    print(f"   Embedding Preview: {result.embedding_preview}")
    print()
    
    # Cleanup
    await pipeline.shutdown()
    print("✅ Custom embedder example complete!")


if __name__ == "__main__":
    asyncio.run(main())