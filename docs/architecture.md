# VectorShield Architecture

## Overview

VectorShield is an asynchronous ingestion middleware for privacy-safe RAG/vector workflows.
It protects sensitive text before persistence while preserving retrieval quality.

Core idea:
- Embed original text for semantic quality.
- Store only sanitized text in the vector database.

## Processing Flow

For each input `Document`:

1. Generate a cache key from original text.
2. Try cache lookup for previously computed PII redaction output.
3. On cache miss:
   - Run PII detection.
   - Run embedding generation.
   - Execute both in parallel when `parallel_processing=true`.
4. Redact text using PII detections.
5. Store:
   - embedding (from original text)
   - sanitized document (redacted text)
   - metadata
6. Emit metrics and optional tracker logs.

## Main Components

- `IngestionPipeline`
  - Orchestrates component lifecycle and document processing.
- `PIIDetector`
  - Detects PII entities from configured entity set.
- `PIIRedactor`
  - Rewrites sensitive spans into placeholders.
- `CacheBackend`
  - Caches redaction results (`clean_text`, `pii_found`) keyed by text hash.
- `Embedder`
  - Produces vectors from original text.
- `VectorStore`
  - Persists embeddings + sanitized documents.
- `Tracker`
  - Optional observability backend for params/metrics/artifacts.

## Built-in Backends

- Cache:
  - `memory`
  - `redis`
  - `none` (no-op)
- Embedder:
  - `fastembed`
- Vector store:
  - `chroma`
- Tracker:
  - `mlflow`
  - `none` (no-op)

## Extensibility Model

`ComponentLoader` supports three integration modes per component:

1. Pass a concrete custom instance implementing the interface.
2. Pass functions and use generic wrappers (`GenericCache`, `GenericEmbedder`, `GenericVectorStore`).
3. Use built-in backend selected by config.

This keeps project code decoupled from vendor SDKs.

## Data Boundaries

- In memory during processing:
  - Original text
  - PII detection results
  - Embedding vectors
- Persisted in vector store:
  - Sanitized text only
  - Embeddings
  - Metadata
- Persisted in cache:
  - Sanitized text + detected PII labels
  - No raw original text unless a custom backend is implemented that does so

## Lifecycle

- `await pipeline.initialize()`
  - Connects cache, vector store, tracker.
- `await pipeline.process_document(...)` / `process_batch(...)`
  - Executes ingestion.
- `await pipeline.shutdown()`
  - Closes component connections.
