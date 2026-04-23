# API Reference

## Document

```python
Document(id: str, text: str, metadata: Optional[Dict] = None)
```

Input document for ingestion.

| Attribute | Type | Description |
|--------|----|----|
| `id` | `str` | Unique document identifier |
| `text` | `str` | Raw document text that may contain PII |
| `metadata` | `dict` | Arbitrary metadata stored alongside the embedding |

## ProcessedDocument

Returned by `process_document`. Call `.to_dict()` for a JSON-serializable form.

| Attribute | Type | Description |
|--------|----|----|
| `id` | `str` | Document ID |
| `original_preview` | `str` | First 100 chars of original text |
| `clean_text` | `str` | Sanitized text with PII replaced by tokens |
| `pii_entities` | `List[str]` | Entity types found such as `PERSON` or `EMAIL_ADDRESS` |
| `embedding_preview` | `List[float]` | First 5 values of the embedding vector |
| `metadata` | `dict` | Original metadata |
| `status` | `str` | `"success"` or `"failed"` |

## IngestionPipeline

```python
IngestionPipeline(
    config: Optional[Dict] = None,
    cache: Optional[CacheBackend] = None,
    embedder: Optional[Embedder] = None,
    vectorstore: Optional[VectorStore] = None,
    tracker: Optional[Tracker] = None,
    pii_policy: Optional[PIIPolicy] = None,
    embed_func=None,
    embed_batch_func=None,
    cache_get_func=None,
    cache_set_func=None,
    add_vectors_func=None,
    search_func=None,
)
```

### Core Methods

#### `await pipeline.initialize()`

Connect all components. Must be called before processing.

#### `await pipeline.shutdown()`

Disconnect all components and flush pending data.

#### `await pipeline.process_document(doc: Document) -> ProcessedDocument`

Process a single document through the full pipeline.

#### `await pipeline.process_batch(docs: List[Document]) -> Dict`

Process multiple documents concurrently.

Example response:

```json
{
  "batch_id": "uuid",
  "total_processed": 10,
  "total_time_seconds": 1.23,
  "results": [{ "...": "ProcessedDocument.to_dict()" }]
}
```

#### `pipeline.get_metrics() -> Dict`

Return aggregate ingestion metrics summary.

#### `pipeline.reset_metrics()`

Reset ingestion metrics counters.

#### `await pipeline.retrieve(query_text: str, top_k: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict]`

Run retrieval against the stored sanitized corpus.

#### `pipeline.get_storage_info() -> Dict`

Return vector store persistence information when the backend supports it.

#### `await pipeline.peek_storage(limit: int = 10) -> List[Dict]`

Return a small sample of stored records when the backend supports it.

## Retrieval Metrics

LexiRedact exposes standalone retrieval evaluation helpers in `lexiredact.metrics`.

```python
from lexiredact.metrics import RetrievalMetricsEvaluator
```

#### `RetrievalMetricsEvaluator.reciprocal_rank(expected_ids, retrieved_ids) -> float`

Compute reciprocal rank for a single query.

#### `RetrievalMetricsEvaluator.recall_at_k(expected_ids, retrieved_ids, k) -> float`

Compute recall at a given cutoff.

#### `RetrievalMetricsEvaluator.evaluate_query(query_id, expected_ids, retrieved_ids, k=5) -> Dict`

Evaluate one query and return per-query retrieval metrics.

#### `RetrievalMetricsEvaluator.evaluate_queries(queries, k=5) -> Dict`

Evaluate multiple queries and return a summary plus per-query metrics.

## Interfaces

All interfaces are abstract base classes that custom implementations must satisfy.

### CacheBackend

```python
async def connect() -> None
async def close() -> None
async def get(key: str) -> Optional[Dict]
async def set(key: str, value: Dict, ttl: int = 3600) -> None
async def delete(key: str) -> None
```

### Embedder

```python
async def embed_text(text: str) -> List[float]
async def embed_batch(texts: List[str]) -> List[List[float]]
def get_embedding_dimension() -> int
```

### VectorStore

```python
async def connect() -> None
async def close() -> None
async def add_vectors(ids, embeddings, documents, metadata) -> None
async def query(query_embedding, top_k, filter_metadata) -> List[Dict]
async def delete(ids) -> None
```

### Tracker

```python
async def connect() -> None
async def close() -> None
async def log_metric(key, value, step) -> None
async def log_metrics(metrics: Dict, step) -> None
async def log_param(key, value) -> None
async def log_artifact(file_path, artifact_path) -> None
```
