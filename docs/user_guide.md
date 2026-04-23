# LexiRedact User Guide

This guide gives a complete walkthrough of LexiRedact from first use to advanced configuration.

Use this document when you want to understand:

- what LexiRedact does
- how to process documents
- what the default settings are
- how to change defaults
- how to add custom pattern recognition
- how to inspect stored data
- how to retrieve from the sanitized corpus
- how to use chunking, caching, tracking, and custom integrations

## 1. What LexiRedact Does

LexiRedact is a privacy-preserving ingestion layer for RAG and vector database workflows.

Its processing model is:

1. take raw input text
2. detect PII using Presidio
3. redact the text
4. generate embeddings from the original text
5. store only the sanitized text plus embeddings in the vector store

This gives better retrieval quality than embedding already-redacted text, while still avoiding raw PII storage in the vector database.

## 2. Core Concepts

### `Document`

Input object for ingestion:

```python
from lexiredact import Document

doc = Document(
    id="doc-1",
    text="Contact John Doe at john@example.com",
    metadata={"source": "crm", "domain": "sales"},
)
```

### `IngestionPipeline`

Main class that orchestrates:

- cache
- PII detection
- redaction
- embedding generation
- vector storage
- metrics and tracking

### `ProcessedDocument`

Result object returned by `process_document(...)`. It includes:

- `id`
- `status`
- `original_preview`
- `clean_text`
- `pii_found`
- `vector_preview`
- `metadata`

## 3. Install and Import

Basic import:

```python
import lexiredact as vs
```

If you want YAML config support:

```bash
pip install pyyaml
```

If you want Redis support:

```bash
pip install "redis[async]"
```

If you want MLflow tracking:

```bash
pip install mlflow
```

If you want PDF chunking support:

```bash
pip install pypdf
```

## 4. Quick Start

```python
import asyncio
import lexiredact as vs


async def main():
    pipeline = vs.IngestionPipeline()
    await pipeline.initialize()

    doc = vs.Document(
        id="1",
        text="John Doe can be reached at john.doe@example.com or 555-123-4567.",
        metadata={"source": "demo"},
    )

    result = await pipeline.process_document(doc)
    print(result.to_dict())

    await pipeline.shutdown()


asyncio.run(main())
```

Expected behavior:

- `PERSON`, `EMAIL_ADDRESS`, and phone-like values are detected when supported by the configured recognizers
- `clean_text` contains redacted placeholders
- only the sanitized text is stored in the vector store

## 5. Processing Multiple Documents

```python
import asyncio
import lexiredact as vs


async def main():
    pipeline = vs.IngestionPipeline()
    await pipeline.initialize()

    docs = [
        vs.Document(id="1", text="Call John at 555-123-4567", metadata={"source": "crm"}),
        vs.Document(id="2", text="Email Alice at alice@example.com", metadata={"source": "support"}),
    ]

    result = await pipeline.process_batch(docs)
    print(result)

    await pipeline.shutdown()


asyncio.run(main())
```

Batch output includes:

- `batch_id`
- `total_processed`
- `total_time_seconds`
- `results`

## 6. Default Configuration

Current defaults in the project are:

```python
{
    "pii_entities": [
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "US_SSN",
        "LOCATION",
        "DATE_TIME",
        "MEDICAL_LICENSE",
        "US_PASSPORT",
    ],
    "presidio_language": "en",
    "presidio_score_threshold": 0.0,
    "presidio_allow_list": [],
    "presidio_allow_list_match": "exact",
    "presidio_custom_patterns": [],
    "presidio_operator_map": {},
    "presidio_default_replacement": "<{entity_type}>",
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "embedding_batch_size": 32,
    "cache_backend": "memory",
    "cache_ttl": 3600,
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    "vectorstore_backend": "chroma",
    "vectorstore_path": "./lexiredact_data",
    "vectorstore_collection": "documents",
    "parallel_processing": True,
    "max_batch_size": 1000,
    "tracking_enabled": False,
    "tracking_backend": "none",
    "mlflow_tracking_uri": "http://localhost:5000",
    "mlflow_experiment_name": "lexiredact",
    "enable_async": True,
    "timeout_seconds": 30,
}
```

## 7. How to Change Defaults

There are three common ways to change configuration.

### Option A: Inline dictionary

```python
import lexiredact as vs

config = vs.load_config(config_dict={
    "embedding_model": "BAAI/bge-base-en-v1.5",
    "cache_backend": "redis",
    "redis_host": "localhost",
    "redis_port": 6379,
    "vectorstore_collection": "hr_documents",
    "parallel_processing": True,
    "max_batch_size": 200,
})

pipeline = vs.IngestionPipeline(config=config)
```

### Option B: YAML file

Create `config.yaml`:

```yaml
embedding_model: BAAI/bge-base-en-v1.5
cache_backend: redis
redis_host: localhost
redis_port: 6379
vectorstore_backend: chroma
vectorstore_path: ./lexiredact_data
vectorstore_collection: hr_documents
parallel_processing: true
max_batch_size: 200
```

Load it:

```python
import lexiredact as vs

config = vs.load_config(config_file="config.yaml")
pipeline = vs.IngestionPipeline(config=config)
```

### Option C: Save a template and edit it

```python
import lexiredact as vs

config = vs.get_default_config()
config["cache_backend"] = "redis"
config["vectorstore_collection"] = "legal_docs"

vs.save_config_to_yaml(config, "lexiredact_config.yaml")
```

## 8. Key Parameters and What They Control

### PII detection

- `pii_entities`: which entity types to detect
- `presidio_language`: language used by Presidio
- `presidio_score_threshold`: lower values detect more, higher values are stricter
- `presidio_allow_list`: values or patterns to leave unchanged
- `presidio_allow_list_match`: `exact` or `regex`
- `presidio_custom_patterns`: custom regex recognizers

### Redaction behavior

- `presidio_operator_map`: per-entity replacement behavior
- `presidio_default_replacement`: fallback replacement template

### Embedding behavior

- `embedding_model`: built-in FastEmbed model name
- `embedding_batch_size`: preferred embedding batch size

### Cache behavior

- `cache_backend`: `memory`, `redis`, or `none`
- `cache_ttl`: cache lifetime in seconds
- `redis_host`, `redis_port`, `redis_db`: Redis connection settings

### Storage behavior

- `vectorstore_backend`: `chroma` or `custom`
- `vectorstore_path`: local Chroma persistence path
- `vectorstore_collection`: logical collection name

### Performance and operations

- `parallel_processing`: run embedding and PII detection in parallel
- `max_batch_size`: maximum size accepted by `process_batch(...)`
- `timeout_seconds`: timeout budget for processing

### Tracking

- `tracking_enabled`: turn experiment tracking on or off
- `tracking_backend`: `mlflow` or `none`
- `mlflow_tracking_uri`: MLflow server URL
- `mlflow_experiment_name`: experiment name

## 9. Custom Pattern Recognition

This is how you teach LexiRedact to detect organization-specific IDs or codes that Presidio does not provide by default.

Common examples:

- employee IDs
- customer codes
- ticket numbers
- internal case references

### Example: detect `EMP123456`

```python
import lexiredact as vs

config = vs.load_config(config_dict={
    "pii_entities": [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "EMPLOYEE_ID",
    ],
    "presidio_custom_patterns": [
        {
            "entity_name": "EMPLOYEE_ID",
            "regex_pattern": r"\bEMP\d{6}\b",
            "score": 0.85,
        }
    ],
    "presidio_operator_map": {
        "EMPLOYEE_ID": {
            "operator": "replace",
            "params": {"new_value": "<EMPLOYEE_ID>"},
        }
    },
    "presidio_default_replacement": "<{entity_type}>",
})
```

Important rules:

1. add the custom entity name to `pii_entities`
2. define its regex in `presidio_custom_patterns`
3. optionally define a custom replacement in `presidio_operator_map`
4. if you do not define an operator, `presidio_default_replacement` is used

### YAML version

```yaml
pii_entities:
  - PERSON
  - EMAIL_ADDRESS
  - PHONE_NUMBER
  - EMPLOYEE_ID

presidio_custom_patterns:
  - entity_name: EMPLOYEE_ID
    regex_pattern: "\\bEMP\\d{6}\\b"
    score: 0.85

presidio_operator_map:
  EMPLOYEE_ID:
    operator: replace
    params:
      new_value: "<EMPLOYEE_ID>"

presidio_default_replacement: "<{entity_type}>"
```

## 10. Allow List and False Positives

Use the allow list when there are values you do not want redacted.

### Exact matching

```python
config = vs.load_config(config_dict={
    "presidio_allow_list": [
        "LexiRedact",
        "support@company.internal",
    ],
    "presidio_allow_list_match": "exact",
})
```

### Regex matching

```python
config = vs.load_config(config_dict={
    "presidio_allow_list": [
        r"support@company\.internal",
        r"VS-\d{4}",
    ],
    "presidio_allow_list_match": "regex",
})
```

Use this carefully. If the allow list is too broad, sensitive values may remain unredacted.

## 11. Custom Redaction Behavior

By default, LexiRedact uses:

```python
"<{entity_type}>"
```

So a `PERSON` becomes `<PERSON>` and an `EMAIL_ADDRESS` becomes `<EMAIL_ADDRESS>`.

If you want entity-specific replacements:

```python
config = vs.load_config(config_dict={
    "presidio_operator_map": {
        "PERSON": {
            "operator": "replace",
            "params": {"new_value": "<PERSON>"},
        },
        "EMAIL_ADDRESS": {
            "operator": "replace",
            "params": {"new_value": "<EMAIL>"},
        },
    },
    "presidio_default_replacement": "<{entity_type}>",
})
```

This lets you normalize output more aggressively.

## 12. Chunking Large Documents

LexiRedact includes a chunking module at:

```python
lexiredact.chunking
```

Example:

```python
from lexiredact.chunking import (
    DocumentChunker,
    ChunkingStrategy,
    JSONExporter,
)

chunker = DocumentChunker(
    chunk_size=512,
    overlap=100,
    strategy=ChunkingStrategy.HYBRID,
)

chunks = chunker.chunk_text(
    text="Large source document text here",
    doc_id="policy_2026",
    metadata={"source": "policy.pdf", "domain": "hr"},
)

JSONExporter.to_cli_input(chunks, output_path="chunked_cli.json")
```

Then run:

```bash
lexiredact process -i chunked_cli.json -o output.json
```

For a full chunking walkthrough, see `docs/chunking.md`.

## 13. Retrieval

After ingestion, you can query the sanitized corpus:

```python
import asyncio
import lexiredact as vs


async def main():
    pipeline = vs.IngestionPipeline()
    await pipeline.initialize()

    results = await pipeline.retrieve(
        query_text="employee onboarding contact details",
        top_k=5,
        filter_metadata={"domain": "hr"},
    )
    print(results)

    await pipeline.shutdown()


asyncio.run(main())
```

Returned rows generally contain:

- `id`
- `document`
- `score`
- `metadata`

## 14. Inspecting What Was Stored

If the backend supports it, you can inspect collection metadata and sample stored rows.

```python
import asyncio
import lexiredact as vs


async def main():
    pipeline = vs.IngestionPipeline()
    await pipeline.initialize()

    print(pipeline.get_storage_info())
    print(await pipeline.peek_storage(limit=5))

    await pipeline.shutdown()


asyncio.run(main())
```

CLI equivalents:

```bash
lexiredact inspect --limit 5
lexiredact retrieve -q "employee onboarding" -k 5
```

## 15. Metrics and Tracking

You can inspect runtime metrics:

```python
metrics = pipeline.get_metrics()
print(metrics)
```

Reset them when needed:

```python
pipeline.reset_metrics()
```

To enable MLflow tracking:

```python
config = vs.load_config(config_dict={
    "tracking_enabled": True,
    "tracking_backend": "mlflow",
    "mlflow_tracking_uri": "http://localhost:5000",
    "mlflow_experiment_name": "lexiredact",
})
```

Use tracking only when you need observability. Metadata and metrics should still be reviewed for privacy.

## 16. Cache Backends

### Memory cache

Default option. Good for local runs and simple deployments.

```python
config = vs.load_config(config_dict={
    "cache_backend": "memory",
    "cache_ttl": 3600,
})
```

### Redis cache

Useful when you want shared or persistent caching across workers.

```python
config = vs.load_config(config_dict={
    "cache_backend": "redis",
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    "cache_ttl": 3600,
})
```

### Disable caching

```python
config = vs.load_config(config_dict={
    "cache_backend": "none",
})
```

## 17. Custom Embedders and Vector Stores

LexiRedact supports:

- direct class-based integration
- function-based integration

Examples:

```python
pipeline = vs.IngestionPipeline(
    embed_func=my_embed_function,
    add_vectors_func=my_add_vectors,
    search_func=my_search_vectors,
)
```

Or:

```python
pipeline = vs.IngestionPipeline(
    embedder=my_embedder_instance,
    vectorstore=my_vectorstore_instance,
)
```

For detailed integration examples, see `docs/integrations.md`.

## 18. CLI Usage

Process documents from a JSON file:

```json
{
  "documents": [
    {
      "id": "1",
      "text": "Call John at 555-123-4567",
      "metadata": {"source": "crm"}
    }
  ]
}
```

Commands:

```bash
lexiredact process -i input.json -o output.json
lexiredact process -i input.json --stats
lexiredact inspect --limit 5
lexiredact retrieve -q "john contact" -k 5
```

Important:

- the CLI expects `{"documents": [...]}` as input
- a raw JSON list is not accepted directly by the current CLI

## 19. Practical Recommendations

- keep metadata flat and JSON-friendly
- keep `parallel_processing=true` unless debugging
- start with the default FastEmbed model unless you have a reason to change it
- use custom patterns for domain-specific identifiers
- review allow-list rules carefully
- chunk large source documents before ingestion
- inspect sanitized storage periodically

## 20. Common Mistakes

- forgetting to call `await pipeline.initialize()`
- forgetting to call `await pipeline.shutdown()`
- sending a raw list to the CLI instead of wrapping it in `documents`
- adding a custom regex pattern without adding the entity to `pii_entities`
- using nested metadata structures when simple values would work better
- setting `max_batch_size` smaller than your actual workload
- allowing too many values through the allow list

## 21. Related Documentation

- `docs/api.md`
- `docs/configuration.md`
- `docs/cli.md`
- `docs/chunking.md`
- `docs/integrations.md`
- `docs/privacy_model.md`
