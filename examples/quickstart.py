"""
VectorShield Quickstart Example

Demonstrates the simplest usage with default settings.
No configuration required - works out of the box.
"""
import asyncio
import vectorshield as vs


async def main():
    """Quickstart example."""
    
    print("=" * 60)
    print("VectorShield Quickstart Example")
    print("=" * 60)
    print()
    
    # Step 1: Create pipeline with defaults
    # - Memory cache (no Redis required)
    # - FastEmbed embeddings (BAAI/bge-small-en-v1.5)
    # - ChromaDB storage (./vectorshield_data)
    print("Creating pipeline with default configuration...")
    pipeline = vs.IngestionPipeline()
    
    # Step 2: Initialize (connects all components)
    await pipeline.initialize()
    print()
    
    # Step 3: Process sample documents
    print("Processing documents with PII...")
    documents = [
        vs.Document(
            id="doc1",
            text="Contact John Smith at john.smith@email.com or call 555-123-4567",
            metadata={"source": "customer_service"}
        ),
        vs.Document(
            id="doc2",
            text="Patient Sarah Johnson, DOB: 01/15/1985, SSN: 123-45-6789",
            metadata={"source": "medical_records"}
        ),
        vs.Document(
            id="doc3",
            text="The product launch is scheduled for next quarter in New York",
            metadata={"source": "internal_memo"}
        ),
    ]
    
    # Process documents (concurrent batch processing)
    result = await pipeline.process_batch(documents)
    
    print(f"\n📊 Batch Results:")
    print(f"   Total Processed: {result['total_processed']}")
    print(f"   Total Time: {result['total_time_seconds']}s")
    print()
    
    # Display results
    for doc_result in result['results']:
        print(f"📄 Document: {doc_result['id']}")
        print(f"   Status: {doc_result['status']}")
        print(f"   Original: {doc_result['original_preview']}")
        print(f"   Sanitized: {doc_result['clean_text']}")
        print(f"   PII Found: {doc_result['pii_found']}")
        print(f"   Embedding Preview: {doc_result['vector_preview']}")
        print()
    
    # Step 4: Get metrics
    metrics = pipeline.get_metrics()
    print("📈 Performance Metrics:")
    print(f"   Documents Processed: {metrics['overview']['total_documents']}")
    print(f"   Success Rate: {metrics['overview']['success_rate']}")
    print(f"   PII Entities Redacted: {metrics['privacy']['total_pii_entities_redacted']}")
    print(f"   Unique PII Types: {metrics['privacy']['unique_pii_types']}")
    print(f"   Average Latency: {metrics['performance']['avg_latency_ms']} ms")
    print(f"   Privacy Overhead: {metrics['performance']['privacy_overhead_percent']}%")
    print(f"   Cache Hit Rate: {metrics['caching']['cache_hit_rate']}")
    print()
    
    # Step 5: Cleanup
    await pipeline.shutdown()
    print("✅ Example complete!")


if __name__ == "__main__":
    asyncio.run(main())