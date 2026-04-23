# LexiRedact

LexiRedact is a Python package for privacy-first document ingestion in RAG and vector database workflows. It detects PII, redacts sensitive text before storage, and preserves retrieval quality by generating embeddings from the original text while storing only sanitized content.

## Install

```bash
pip install lexiredact
```

Optional extras:

```bash
pip install "lexiredact[pdf]"
pip install "lexiredact[redis]"
pip install "lexiredact[mlflow]"
pip install "lexiredact[all]"
```

## What It Focuses On

- PII detection with Presidio
- safe redaction before vector-store persistence
- configurable ingestion pipeline components
- operational metrics for privacy and latency
- optional retrieval evaluation helpers for model comparison

## Quick Start

```python
import asyncio
import lexiredact as lr


async def main() -> None:
    pipeline = lr.IngestionPipeline()
    await pipeline.initialize()

    result = await pipeline.process_document(
        lr.Document(
            id="doc-1",
            text="Contact Jane Doe at jane@example.com or 555-0101",
            metadata={"source": "demo"},
        )
    )

    print(result.clean_text)
    print(result.pii_entities)

    await pipeline.shutdown()


asyncio.run(main())
```

## Docs And Examples

- docs: [`docs/`](./docs)
- examples: [`examples/`](./examples)
