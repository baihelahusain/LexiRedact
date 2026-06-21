# Architecture

LexiRedact is organized around one public pipeline entry point:

```python
LexiredactPipeline(config, embedder=None, store=None)
```

## Components

- `config`: Pydantic models and YAML loader.
- `adapters`: maps user dictionaries into internal chunks.
- `pipeline.pii`: Presidio detection and anonymization.
- `pipeline.embedder`: built-in and custom embedding backends.
- `pipeline.store`: vector-store interface and Chroma implementation.
- `cache`: optional Redis embedding cache.
- `models`: result contracts returned to callers.
- `cli`: command-line wrapper around the same public API.

## Ingestion sequence

```text
raw user dicts
  -> ChunkAdapter
  -> Orchestrator
  -> PII detector/redactor depending on mode
  -> EmbedderBase
  -> VectorStoreBase
  -> ProcessingResult[]
```

Invalid input chunks are filtered by `ChunkAdapter`. Storage failures are raised so ingestion failure is not silent.

## Mode-specific execution

`dual`:

```text
detect -> asyncio.gather(redact, embed original) -> store sanitized metadata
```

`preredacted`:

```text
detect -> redact -> embed sanitized -> store sanitized metadata
```

`raw`:

```text
embed original -> store original metadata
```

## Extension points

Use custom integrations through constructor injection:

```python
pipeline = LexiredactPipeline(config, embedder=my_embedder, store=my_store)
```

This avoids changing LexiRedact internals and keeps application-specific storage or model code outside the package.
