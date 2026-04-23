# Chunking Guide

Use the `lexiredact.chunking` module to split large text or PDFs into smaller chunks before sending them through the LexiRedact ingestion pipeline.

This guide shows:

- how to chunk text
- how to chunk PDFs
- how to export chunk output
- how to create CLI-ready JSON for `lexiredact process`
- what JSON shape LexiRedact expects

## Imports

```python
from pathlib import Path

from lexiredact.chunking import (
    DocumentChunker,
    ChunkingStrategy,
    PDFLoader,
    JSONExporter,
)
from lexiredact.pipeline import Document, IngestionPipeline
```

## 1. Chunk Plain Text

```python
from lexiredact.chunking import DocumentChunker, ChunkingStrategy

text = """
Employee John Doe can be reached at john.doe@example.com.
Call him at 415-555-0123 for onboarding questions.
"""

chunker = DocumentChunker(
    chunk_size=200,
    overlap=50,
    strategy=ChunkingStrategy.FIXED_SIZE,
    preserve_sentences=True,
)

chunks = chunker.chunk_text(
    text=text,
    doc_id="employee_handbook",
    metadata={
        "source": "employee_handbook.txt",
        "domain": "hr",
        "sensitivity": "sensitive",
    },
)

print(f"Created {len(chunks)} chunks")
print(chunks[0].id)
print(chunks[0].text)
print(chunks[0].metadata)
```

Each chunk contains:

- `id`
- `text`
- `chunk_index`
- `start_char`
- `end_char`
- `metadata`

## 2. Chunk a PDF

```python
from pathlib import Path
from lexiredact.chunking import DocumentChunker, ChunkingStrategy, PDFLoader

pdf_path = "sample.pdf"

text = PDFLoader.extract_text(pdf_path)
pdf_metadata = PDFLoader.extract_metadata(pdf_path)

chunker = DocumentChunker(
    chunk_size=512,
    overlap=100,
    strategy=ChunkingStrategy.HYBRID,
)

chunks = chunker.chunk_text(
    text=text,
    doc_id=Path(pdf_path).stem,
    metadata={
        **pdf_metadata,
        "source": Path(pdf_path).name,
        "domain": "documents",
        "sensitivity": "sensitive",
    },
)
```

If PDF support is missing, install the PDF dependency used by the loader:

```bash
pip install pypdf
```

## 3. Export Chunk Output

### Raw LexiRedact document list

Use this when you want to load the JSON yourself in Python and convert each row into `Document(...)`.

```python
from lexiredact.chunking import JSONExporter

JSONExporter.to_lexiredact_format(
    chunks,
    output_path="chunked_text.json",
)
```

Output shape:

```json
[
  {
    "id": "employee_handbook_chunk_0",
    "text": "Employee John Doe can be reached at john.doe@example.com.",
    "metadata": {
      "source": "employee_handbook.txt",
      "domain": "hr",
      "sensitivity": "sensitive",
      "chunk_index": 0
    }
  }
]
```

### CLI-ready JSON

Use this when you want to run:

```bash
lexiredact process -i chunked_cli.json
```

Export it like this:

```python
from lexiredact.chunking import JSONExporter

JSONExporter.to_cli_input(
    chunks,
    output_path="chunked_cli.json",
)
```

Output shape:

```json
{
  "documents": [
    {
      "id": "employee_handbook_chunk_0",
      "text": "Employee John Doe can be reached at john.doe@example.com.",
      "metadata": {
        "source": "employee_handbook.txt",
        "domain": "hr",
        "sensitivity": "sensitive",
        "chunk_index": 0
      }
    }
  ]
}
```

Important:

- `lexiredact process` expects `{"documents": [...]}`.
- A raw JSON list will not work directly with the current CLI.

## 4. Process Chunks with the Python API

If you want to process chunks directly in Python instead of using the CLI:

```python
import asyncio
from lexiredact.pipeline import Document, IngestionPipeline

async def main():
    pipeline = IngestionPipeline()
    await pipeline.initialize()

    for chunk in chunks:
        doc = Document(
            id=chunk.id,
            text=chunk.text,
            metadata=chunk.metadata,
        )
        result = await pipeline.process_document(doc)
        print(result.to_dict())

    await pipeline.shutdown()

asyncio.run(main())
```

## 5. Process Chunked JSON with the CLI

First export CLI-ready JSON:

```python
JSONExporter.to_cli_input(chunks, output_path="chunked_cli.json")
```

Then run:

```bash
lexiredact process -i chunked_cli.json -o output.json
```

The output will contain:

- `batch_id`
- `total_processed`
- `total_time_seconds`
- `results`

Each item in `results` includes:

- `id`
- `status`
- `original_preview`
- `clean_text`
- `pii_found`
- `vector_preview`
- `metadata`

## 6. Recommended Metadata

Recommended metadata fields for chunked documents:

- `source`
- `domain`
- `sensitivity`
- `chunk_index`
- `source_doc_id`

Example:

```json
{
  "source": "policy.pdf",
  "domain": "hr",
  "sensitivity": "sensitive",
  "chunk_index": 3,
  "source_doc_id": "policy_2026"
}
```

Keep metadata flat when possible. Primitive values work best:

- strings
- integers
- floats
- booleans

## 7. Recommended Strategies

Use these defaults unless you have a stronger reason:

- `FIXED_SIZE` for simple pipelines and predictable chunk sizes
- `HYBRID` for better readability and better sentence grouping
- `chunk_size=512` and `overlap=100` for general document ingestion

Start smaller if documents are noisy or contain dense PII.

## 8. Common Mistakes

- Passing a raw JSON list to `lexiredact process` instead of wrapping it in `documents`
- Forgetting to include stable `id` values for each chunk
- Putting deeply nested objects in metadata when simple fields are enough
- Using very large chunks, which can reduce retrieval quality and make redaction harder to inspect

## 9. End-to-End Example

```python
from pathlib import Path
from lexiredact.chunking import (
    DocumentChunker,
    ChunkingStrategy,
    PDFLoader,
    JSONExporter,
)

pdf_path = "employee_policy.pdf"
text = PDFLoader.extract_text(pdf_path)

chunker = DocumentChunker(
    chunk_size=512,
    overlap=100,
    strategy=ChunkingStrategy.HYBRID,
)

chunks = chunker.chunk_text(
    text=text,
    doc_id=Path(pdf_path).stem,
    metadata={
        "source": Path(pdf_path).name,
        "domain": "hr",
        "sensitivity": "sensitive",
    },
)

JSONExporter.to_cli_input(
    chunks,
    output_path="employee_policy_chunks.json",
)
```

Then run:

```bash
lexiredact process -i employee_policy_chunks.json -o processed_output.json
```
