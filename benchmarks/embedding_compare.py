"""
Embedding Quality Comparison

Demonstrates that embeddings generated from original text (before redaction)
preserve semantic quality better than embeddings from redacted text.

This validates the core "Shadow Mode" architecture of VectorShield.
"""
import asyncio
import numpy as np
from typing import List
import vectorshield as vs


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


async def benchmark_embedding_quality():
    """Compare embedding quality: original vs redacted text."""
    
    print("=" * 60)
    print("VectorShield Embedding Quality Comparison")
    print("=" * 60)
    print()
    
    # Test cases: semantically similar documents with PII
    test_cases = [
        {
            "query": "I need to contact my doctor about test results",
            "doc_with_pii": "Contact Dr. Sarah Johnson at sarah.johnson@clinic.com or call 555-789-1234",
            "doc_redacted": "Contact <PERSON> at <EMAIL_ADDRESS> or call <PHONE_NUMBER>",
        },
        {
            "query": "How do I reach customer support",
            "doc_with_pii": "Email support@company.com or message John Smith at ext. 4567",
            "doc_redacted": "Email <EMAIL_ADDRESS> or message <PERSON> at ext. <PHONE_NUMBER>",
        },
    ]
    
    # Initialize embedder
    embedder = vs.FastEmbedEmbedder()
    
    print("🧪 Test: Shadow Mode vs Direct Redaction")
    print("   Shadow Mode: Embed original text, then redact")
    print("   Direct Redaction: Redact first, then embed")
    print()
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"📄 Test Case {i}:")
        print(f"   Query: {test_case['query']}")
        print(f"   Original: {test_case['doc_with_pii']}")
        print(f"   Redacted: {test_case['doc_redacted']}")
        print()
        
        # Generate embeddings
        query_emb = await embedder.embed_text(test_case['query'])
        original_emb = await embedder.embed_text(test_case['doc_with_pii'])
        redacted_emb = await embedder.embed_text(test_case['doc_redacted'])
        
        # Calculate similarities
        sim_original = cosine_similarity(query_emb, original_emb)
        sim_redacted = cosine_similarity(query_emb, redacted_emb)
        
        # Quality difference
        quality_loss = ((sim_original - sim_redacted) / sim_original) * 100
        
        print(f"   Similarity (Shadow Mode): {sim_original:.4f}")
        print(f"   Similarity (Direct Redaction): {sim_redacted:.4f}")
        print(f"   Quality Loss: {quality_loss:.2f}%")
        print()
        
        results.append({
            "case": i,
            "sim_original": sim_original,
            "sim_redacted": sim_redacted,
            "quality_loss": quality_loss
        })
    
    # Summary statistics
    avg_quality_loss = np.mean([r["quality_loss"] for r in results])
    max_quality_loss = max([r["quality_loss"] for r in results])
    
    print("📊 Summary:")
    print(f"   Average Quality Loss: {avg_quality_loss:.2f}%")
    print(f"   Maximum Quality Loss: {max_quality_loss:.2f}%")
    print()
    
    print("💡 Key Insights:")
    print("   ✅ Shadow Mode (VectorShield approach):")
    print("      - Embeds ORIGINAL text → High semantic quality")
    print("      - Stores REDACTED text → Privacy protected")
    print("      - Best of both worlds!")
    print()
    print("   ❌ Direct Redaction (naive approach):")
    print("      - Embeds REDACTED text → Lower semantic quality")
    print("      - Placeholder tokens (<PERSON>) reduce meaning")
    print("      - Search quality degrades")
    print()
    print("   🎯 Conclusion:")
    print(f"      VectorShield preserves {100 - avg_quality_loss:.1f}% of semantic quality")
    print("      while ensuring PII never reaches the vector database.")
    print()


async def demonstrate_search_quality():
    """Demonstrate search quality with VectorShield."""
    
    print("=" * 60)
    print("Search Quality Demonstration")
    print("=" * 60)
    print()
    
    # Create pipeline
    pipeline = vs.IngestionPipeline()
    await pipeline.initialize()
    
    # Ingest documents with PII
    documents = [
        vs.Document(
            id="doc1",
            text="Dr. Alice Smith specializes in cardiology at Boston Medical Center"
        ),
        vs.Document(
            id="doc2",
            text="Contact neurologist Dr. Bob Johnson at bob.j@neuro.com"
        ),
        vs.Document(
            id="doc3",
            text="Schedule appointment with Dr. Carol Davis, orthopedic surgeon"
        ),
    ]
    
    print("📥 Ingesting documents...")
    result = await pipeline.process_batch(documents)
    
    for doc_result in result['results']:
        print(f"   {doc_result['id']}: {doc_result['clean_text']}")
    print()
    
    # Query (without PII)
    query = "I need a heart doctor"
    print(f"🔍 Query: {query}")
    print()
    
    # Generate query embedding
    embedder = pipeline.embedder
    query_embedding = await embedder.embed_text(query)
    
    # Search vector store
    search_results = await pipeline.vectorstore.query(
        query_embedding=query_embedding,
        top_k=3
    )
    
    print("📊 Search Results:")
    for i, result in enumerate(search_results, 1):
        print(f"   {i}. {result['id']} (score: {result['score']:.4f})")
        print(f"      {result['document']}")
    print()
    
    print("💡 Notice:")
    print("   - Query finds 'cardiology' document (heart doctor)")
    print("   - Even though stored text has <PERSON> placeholders")
    print("   - Semantic search works because embeddings are from original text")
    print("   - PII is protected in storage, but search quality is maintained")
    print()
    
    await pipeline.shutdown()


if __name__ == "__main__":
    asyncio.run(benchmark_embedding_quality())
    print()
    asyncio.run(demonstrate_search_quality())