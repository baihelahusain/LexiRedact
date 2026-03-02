"""
Custom Vector Store Example

Demonstrates how to integrate VectorShield with a custom vector database.
Could be: Pinecone, Weaviate, Qdrant, Milvus, or any custom storage.
"""
import asyncio
from typing import List, Dict, Any, Optional
import vectorshield as vs


class CustomVectorStore(vs.VectorStore):
    """
    Example custom vector store implementation.
    
    In production, replace with actual database client logic.
    Could integrate with:
    - Pinecone (cloud vector DB)
    - Weaviate (open source)
    - Qdrant (high performance)
    - Milvus (scalable)
    - Custom storage backend
    """
    
    def __init__(self, connection_string: str = "custom://localhost"):
        """Initialize custom vector store."""
        self.connection_string = connection_string
        self.storage: Dict[str, Dict[str, Any]] = {}  # Mock storage
        print(f"🔧 Initialized custom vector store: {connection_string}")
    
    async def connect(self) -> None:
        """Connect to vector database."""
        # In production: establish actual connection
        print(f"✅ Connected to custom vector store")
    
    async def close(self) -> None:
        """Close connection."""
        print("👋 Closed custom vector store connection")
    
    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add vectors to storage.
        
        In production: call actual vector DB API
        """
        metadata = metadata or [{} for _ in ids]
        
        for doc_id, embedding, document, meta in zip(ids, embeddings, documents, metadata):
            self.storage[doc_id] = {
                "embedding": embedding,
                "document": document,
                "metadata": meta
            }
        
        print(f"   Added {len(ids)} vectors to custom store")
    
    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query for similar vectors.
        
        In production: implement actual similarity search
        """
        # Mock: return all documents with fake scores
        results = []
        for doc_id, data in list(self.storage.items())[:top_k]:
            results.append({
                "id": doc_id,
                "document": data["document"],
                "score": 0.95,  # Mock score
                "metadata": data["metadata"]
            })
        return results
    
    async def delete(self, ids: List[str]) -> None:
        """Delete vectors by ID."""
        for doc_id in ids:
            self.storage.pop(doc_id, None)
        print(f"   Deleted {len(ids)} vectors from custom store")
    
    def count(self) -> int:
        """Get number of vectors stored."""
        return len(self.storage)


async def main():
    """Custom vector store example."""
    
    print("=" * 60)
    print("VectorShield - Custom Vector Store Example")
    print("=" * 60)
    print()
    
    # Create custom vector store instance
    custom_store = CustomVectorStore(connection_string="custom://my-db:5432")
    
    # Create pipeline with custom vector store
    print("Creating pipeline with custom vector store...")
    pipeline = vs.IngestionPipeline(vectorstore=custom_store)
    
    await pipeline.initialize()
    print()
    
    # Process documents
    documents = [
        vs.Document(
            id="store1",
            text="User John Doe registered with email john@example.com",
            metadata={"type": "user_registration"}
        ),
        vs.Document(
            id="store2",
            text="Payment processed for credit card ending in 1234",
            metadata={"type": "payment"}
        ),
    ]
    
    print("Processing documents...")
    result = await pipeline.process_batch(documents)
    
    print(f"\n📊 Results:")
    print(f"   Documents Processed: {result['total_processed']}")
    print(f"   Vectors in Custom Store: {custom_store.count()}")
    print()
    
    # Display what was stored
    for doc_result in result['results']:
        print(f"📄 Stored Document {doc_result['id']}:")
        print(f"   Clean Text: {doc_result['clean_text']}")
        print(f"   PII Redacted: {doc_result['pii_found']}")
        print()
    
    print("💡 Key Points:")
    print("   - Only SANITIZED text is stored in the vector database")
    print("   - Original PII never touches the database")
    print("   - Embeddings are from original text (preserves semantic quality)")
    print("   - Any vector DB can be used via the VectorStore interface")
    print()
    
    # Cleanup
    await pipeline.shutdown()
    print("✅ Custom vector store example complete!")


if __name__ == "__main__":
    asyncio.run(main())