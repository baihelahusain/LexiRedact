"""
Document Chunking Demo

Shows how to:
1. Load PDF or paste large text
2. Chunk into smaller pieces
3. Export as JSON for LexiRedact
"""

import asyncio
from pathlib import Path

from _bootstrap import ensure_project_root

ensure_project_root()

from lexiredact.chunking import (
    DocumentChunker,
    ChunkingStrategy,
    PDFLoader,
    JSONExporter,
)
from lexiredact.pipeline import IngestionPipeline, Document


OUTPUT_DIR = Path(".tmp-build") / "chunking_demo"


# ===== EXAMPLE 1: Chunk large text =====
async def example_text_chunking():
    """Chunk a large paragraph into smaller pieces."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    large_text = """
    LexiRedact is a privacy-preserving middleware for vector databases. 
    It automatically detects and redacts personally identifiable information (PII) 
    before documents are embedded and stored. This ensures that sensitive data 
    never reaches the vector database, protecting user privacy while maintaining 
    semantic search quality through intelligent embedding generation.
    
    The system uses Microsoft Presidio for PII detection and supports multiple 
    vector database backends including ChromaDB, Pinecone, and Weaviate. 
    LexiRedact can be deployed as a middleware layer between your application 
    and vector database, or integrated directly into ingestion pipelines.
    
    Key features include automatic PII redaction, embedding from original text 
    (shadow mode), configurable redaction policies, Redis caching for performance, 
    and comprehensive metrics tracking. The architecture is designed to be 
    production-ready with async/await patterns throughout.
    """
    
    # Create chunker (fixed size: 200 chars, 50 char overlap)
    chunker = DocumentChunker(
        chunk_size=200,
        overlap=50,
        strategy=ChunkingStrategy.FIXED_SIZE,
        preserve_sentences=True,
    )
    
    # Add metadata about this document
    metadata = {
        "source": "demo",
        "domain": "technical",
        "sensitivity": "non_sensitive",
    }
    
    # Chunk the text
    chunks = chunker.chunk_text(
        text=large_text,
        doc_id="lexiredact_guide",
        metadata=metadata
    )
    
    print(f"Created {len(chunks)} chunks from text")
    print("\n--- First Chunk ---")
    print(f"ID: {chunks[0].id}")
    print(f"Text: {chunks[0].text}\n")
    
    # Export to JSON
    json_output = JSONExporter.to_lexiredact_format(chunks)
    print("JSON Output (first chunk):")
    print(json_output[0])
    
    # Save raw list for Python API usage
    output_path = OUTPUT_DIR / "chunked_text.json"
    JSONExporter.to_lexiredact_format(chunks, output_path=output_path)

    # Save CLI-ready payload for `lexiredact process -i`
    cli_output_path = OUTPUT_DIR / "chunked_text_cli.json"
    JSONExporter.to_cli_input(chunks, output_path=cli_output_path)
    print(f"\nSaved to {output_path}\n")


# ===== EXAMPLE 2: Chunk PDF =====
async def example_pdf_chunking():
    """Chunk a PDF file into smaller pieces."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    pdf_path = "sample.pdf"
    
    try:
        # Extract text from PDF
        print(f"Loading PDF: {pdf_path}")
        text = PDFLoader.extract_text(pdf_path)
        metadata = PDFLoader.extract_metadata(pdf_path)
        
        # Then chunk as before
        chunker = DocumentChunker(
            chunk_size=512,
            overlap=100,
            strategy=ChunkingStrategy.HYBRID,  # Use hybrid for better results
        )
        
        chunks = chunker.chunk_text(
            text=text,
            doc_id=Path(pdf_path).stem,
            metadata={**metadata, "domain": "documents"}
        )
        
        print(f"Created {len(chunks)} chunks from PDF")
        
        # Save raw list for Python API usage
        output_path = OUTPUT_DIR / "chunked_pdf.json"
        JSONExporter.to_lexiredact_format(chunks, output_path=output_path)

        # Save CLI-ready payload for `lexiredact process -i`
        cli_output_path = OUTPUT_DIR / "chunked_pdf_cli.json"
        JSONExporter.to_cli_input(chunks, output_path=cli_output_path)
        print(f"Saved to {output_path}")

        # Also save as JSONL for streaming
        JSONExporter.to_jsonl(chunks, OUTPUT_DIR / "chunked_pdf.jsonl")
        print("Saved JSONL format too")
        
    except ImportError as e:
        print(f"Warning: {e}")
        print("Install with: pip install pypdf")


# ===== EXAMPLE 3: Process chunks with LexiRedact =====
async def example_ingest_chunks():
    """Ingest chunked documents through the LexiRedact pipeline."""
    
    # First, chunk the document
    chunker = DocumentChunker(chunk_size=256, strategy=ChunkingStrategy.HYBRID)
    
    sample_text = (
        "Email addresses like john.doe@company.example need to be protected. "
        "Names like John Doe and phone numbers like 415-555-0123 are PII. "
        "Social Security number 457-55-5462 must be redacted."
    )
    
    chunks = chunker.chunk_text(
        text=sample_text,
        doc_id="sensitive_doc",
        metadata={"domain": "hr"}
    )
    
    # Initialize LexiRedact pipeline
    pipeline = IngestionPipeline(
        config={
            "vectorstore_path": str(OUTPUT_DIR / "vectorstore"),
            "vectorstore_collection": "chunking_demo_documents",
            "mlflow_log_artifacts": False,
        }
    )
    await pipeline.initialize()
    
    # Process each chunk through PII detection & embedding
    print("Processing chunks through LexiRedact pipeline:\n")
    
    for chunk in chunks:
        # Convert chunk to LexiRedact Document
        doc = Document(
            id=chunk.id,
            text=chunk.text,
            metadata=chunk.metadata
        )
        
        # Process (PII detection, redaction, embedding)
        result = await pipeline.process_document(doc)
        
        print(f"Chunk ID: {chunk.id}")
        print(f"Original: {chunk.text[:60]}...")
        print(f"Clean:    {result.clean_text[:60]}...")
        print(f"PII Found: {result.pii_entities}")
        print()
    
    await pipeline.shutdown()


# ===== EXAMPLE 4: Different chunking strategies =====
async def example_compare_strategies():
    """Compare different chunking strategies."""
    
    text = """
    This is sentence one. This is sentence two. This is sentence three.
    
    This is paragraph two, sentence one. This is paragraph two, sentence two.
    """
    
    strategies = [
        ChunkingStrategy.FIXED_SIZE,
        ChunkingStrategy.SENTENCE,
        ChunkingStrategy.PARAGRAPH,
        ChunkingStrategy.HYBRID,
    ]
    
    for strategy in strategies:
        chunker = DocumentChunker(
            chunk_size=50,
            overlap=10,
            strategy=strategy,
        )
        
        chunks = chunker.chunk_text(text, "demo", {})
        print(f"\n{strategy.value.upper()} Strategy: {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i}: {len(chunk.text)} chars - {chunk.text[:40]}...")


async def main():
    print("=" * 60)
    print("LexiRedact Document Chunking Examples")
    print("=" * 60)
    
    print("\n1. Text Chunking")
    print("-" * 60)
    await example_text_chunking()
    
    print("\n2. PDF Chunking")
    print("-" * 60)
    await example_pdf_chunking()
    
    print("\n3. Ingesting Chunks with LexiRedact")
    print("-" * 60)
    await example_ingest_chunks()
    
    print("\n4. Strategy Comparison")
    print("-" * 60)
    await example_compare_strategies()


if __name__ == "__main__":
    asyncio.run(main())
