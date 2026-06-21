# API

Import the main user-facing objects from the package root:

```python
from lexiredact import (
    LexiredactPipeline,
    load_config,
    ProcessingResult,
    DetectedEntity,
)
```

## `load_config(source)`

Accepts:

- `dict[str, Any]`
- `str` path
- `pathlib.Path`

Returns a validated `LexiredactConfig`. Raises `LexiredactConfigError` for missing files, invalid YAML, unknown keys, or validation errors.

## `LexiredactPipeline`

```python
pipeline = LexiredactPipeline(config, embedder=None, store=None)
results = pipeline.ingest(raw_chunks)
```

Constructor arguments:

- `config`: a `LexiredactConfig`.
- `embedder`: optional `EmbedderBase` implementation.
- `store`: optional `VectorStoreBase` implementation.

If `embedder` is omitted, the configured backend is created with `create_embedder(config.embedder)`. If `store` is omitted, `ChromaStore` is used.

`ingest(raw_chunks)` accepts a list of dictionaries. It returns one `ProcessingResult` for each valid chunk. Invalid chunks are skipped and logged.

## Result model

`ProcessingResult` fields:

- `chunk_id`
- `sanitized_text`
- `entities_detected`
- `embedding_stored`
- `latency_ms`
- `cache_hit`
- `pipeline_mode`
- `error`
- `stage_latencies`

Use `result.to_dict()` for JSON-ready output.

`DetectedEntity` fields:

- `text`
- `entity_type`
- `start`
- `end`
- `score`

## Custom embedder

```python
from lexiredact.pipeline.embedder.base import EmbedderBase

class MyEmbedder(EmbedderBase):
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 0.0, 1.0] for text in texts]

    def query_embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_batch(texts)

    def get_dimension(self) -> int:
        return 3
```

The return value must be plain Python `list[list[float]]`, in the same order as the input.

## Custom vector store

```python
from typing import Any
from lexiredact.pipeline.store.base import VectorStoreBase

class MyStore(VectorStoreBase):
    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        ...

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def count(self) -> int:
        ...
```

Store implementations should raise `LexiredactStorageError` on write or query failure.

## Exceptions

All public errors inherit from `LexiredactError`:

- `LexiredactConfigError`
- `LexiredactInputError`
- `LexiredactStorageError`
- `LexiredactCacheError`

Cache errors are handled internally by the Redis cache and do not normally reach callers.
