# Custom Integrations

This guide explains how to connect LexiRedact to custom embedders, vector databases, and caches using the current project structure.

LexiRedact supports three integration patterns:

- pass a concrete component instance such as a custom `Embedder` or `VectorStore`
- pass functions such as `embed_func`, `add_vectors_func`, and `search_func`
- use the built-in defaults and override only the part you need

Important behavior to keep in mind:

- embeddings are generated from the original text
- only sanitized text is stored in the vector database
- metadata is passed through to storage and retrieval

## 1. How Integrations Fit Into the Pipeline

The main extension point is `IngestionPipeline(...)`.

You can customize these components:

- `cache`
- `embedder`
- `vectorstore`
- `tracker`

Or provide function-based overrides:

- `cache_get_func`
- `cache_set_func`
- `cache_connect_func`
- `cache_disconnect_func`
- `cache_delete_func`
- `cache_clear_func`
- `embed_func`
- `embed_batch_func`
- `add_vectors_func`
- `search_func`
- `vectorstore_connect_func`
- `vectorstore_disconnect_func`
- `vectorstore_delete_func`
- `vectorstore_update_func`

## 2. Choosing an Integration Style

Use direct instance injection when:

- you want full control
- you already have a class-based client wrapper
- you want to implement the official interfaces

Use function hooks when:

- you already have a client SDK and only need a few operations
- you want the quickest integration
- you do not want to write wrapper classes

## 3. Built-In Defaults

If you do not pass custom integrations, LexiRedact uses its built-in components from configuration.

Common defaults in the current project:

- embedder backend: `fastembed`
- vector store backend: `chroma`
- vector store path: `./lexiredact_data`
- collection name: `documents`

Example:

```python
import lexiredact as vs

pipeline = vs.IngestionPipeline(
    config={
        "embedder_backend": "fastembed",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "vectorstore_backend": "chroma",
        "vectorstore_path": "./lexiredact_data",
        "vectorstore_collection": "documents",
    }
)
```
## 4. Custom Embedder

### Option A: Pass a custom `Embedder` instance

Implement the `Embedder` interface:

```python
import asyncio
from typing import List

import lexiredact as vs


class CustomEmbedder(vs.Embedder):
    def __init__(self, model_name: str = "my-model", dimension: int = 768):
        self.model_name = model_name
        self.dimension = dimension

    async def embed_text(self, text: str) -> List[float]:
        # Replace this with your actual embedding call
        return [0.0] * self.dimension

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(text) for text in texts]

    def get_embedding_dimension(self) -> int:
        return self.dimension


pipeline = vs.IngestionPipeline(
    embedder=CustomEmbedder(model_name="my-model-v1", dimension=768)
)
```

This is the cleanest option when you are building a reusable integration.

### Option B: Pass embedding functions directly

If you already have an embedding SDK client, you can plug it in without creating a class.

```python
from openai import OpenAI
import lexiredact as vs

client = OpenAI(api_key="YOUR_API_KEY")

pipeline = vs.IngestionPipeline(
    config={"embedder_name": "openai"},
    embed_func=lambda text: client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    ).data[0].embedding,
)
```

If your provider supports batch embedding, pass `embed_batch_func` too:

```python
pipeline = vs.IngestionPipeline(
    config={"embedder_name": "openai"},
    embed_func=lambda text: client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    ).data[0].embedding,
    embed_batch_func=lambda texts: [
        item.embedding
        for item in client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
        ).data
    ],
)
```

### What LexiRedact expects from your embedder

- `embed_text(text)` must return `List[float]`
- `embed_batch(texts)` must return `List[List[float]]`
- all embeddings must have the same dimension
- the embedder should be deterministic for the same input when possible

### Practical notes

- LexiRedact embeds the original text before redaction to preserve retrieval quality.
- Your embedder never needs to store anything itself.
- If you only pass `embed_func`, LexiRedact can still work. Batch mode falls back to repeated single calls through the generic embedder wrapper.

## 5. Custom Vector Database

There are two good ways to integrate a vector database:

- implement the `VectorStore` interface
- provide `add_vectors_func` and `search_func`

### VectorStore contract

Your vector store must support these operations:

- `connect()`
- `close()`
- `add_vectors(ids, embeddings, documents, metadata)`
- `query(query_embedding, top_k=5, filter_metadata=None)`
- `delete(ids)`

The important storage rule is:

- `documents` are already sanitized text when `add_vectors(...)` is called

### Option A: Implement a custom `VectorStore`

```python
from typing import Any, Dict, List, Optional
import lexiredact as vs


class CustomVectorStore(vs.VectorStore):
    def __init__(self):
        self.rows: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def add_vectors(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        metadata = metadata or [{} for _ in ids]
        for doc_id, emb, doc, meta in zip(ids, embeddings, documents, metadata):
            self.rows[doc_id] = {
                "embedding": emb,
                "document": doc,
                "metadata": meta,
            }

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for doc_id, row in list(self.rows.items())[:top_k]:
            results.append({
                "id": doc_id,
                "document": row["document"],
                "score": 0.95,
                "metadata": row["metadata"],
            })
        return results

    async def delete(self, ids: List[str]) -> None:
        for doc_id in ids:
            self.rows.pop(doc_id, None)

    def count(self) -> int:
        return len(self.rows)


pipeline = vs.IngestionPipeline(
    vectorstore=CustomVectorStore()
)
```

Use this when you want a proper adapter layer for Pinecone, Qdrant, Weaviate, Milvus, or an internal service.

### Option B: Pass vector store functions directly

This is the fastest integration path if you already have a client object.

```python
from pinecone import Pinecone
import lexiredact as vs

pc = Pinecone(api_key="YOUR_API_KEY")
index = pc.Index("my-index")


def add_vectors(ids, embeddings, documents, metadata):
    metadata = metadata or [{} for _ in ids]
    vectors = []

    for doc_id, emb, doc, meta in zip(ids, embeddings, documents, metadata):
        vectors.append({
            "id": doc_id,
            "values": emb,
            "metadata": {
                **meta,
                "document": doc,
            },
        })

    index.upsert(vectors=vectors)


def search_vectors(query_embedding, top_k, filters):
    response = index.query(
        vector=query_embedding,
        top_k=top_k,
        filter=filters,
        include_metadata=True,
    )

    results = []
    for match in response.matches:
        meta = match.metadata or {}
        results.append({
            "id": match.id,
            "document": meta.get("document"),
            "score": match.score,
            "metadata": meta,
        })
    return results


pipeline = vs.IngestionPipeline(
    config={"vectorstore_name": "pinecone"},
    add_vectors_func=add_vectors,
    search_func=search_vectors,
)
```

### What `add_vectors_func` receives

Your add function is called like this:

```python
add_vectors_func(ids, embeddings, documents, metadata)
```

Arguments:

- `ids`: list of document IDs
- `embeddings`: list of embedding vectors
- `documents`: list of sanitized document strings
- `metadata`: list of metadata dictionaries, or `None`

### What `search_func` must return

Your search function must return a list of dictionaries in this shape:

```python
[
    {
        "id": "doc_1",
        "document": "sanitized document text",
        "score": 0.92,
        "metadata": {"domain": "hr"},
    }
]
```

The keys that matter most are:

- `id`
- `document`
- `score`
- `metadata`

### Optional vector store hooks

If your backend needs lifecycle management, you can also pass:

- `vectorstore_connect_func`
- `vectorstore_disconnect_func`
- `vectorstore_delete_func`

Example:

```python
pipeline = vs.IngestionPipeline(
    add_vectors_func=add_vectors,
    search_func=search_vectors,
    vectorstore_connect_func=lambda: print("connect"),
    vectorstore_disconnect_func=lambda: print("disconnect"),
)
```

## 6. Custom Cache

Caching is optional, but custom cache hooks are useful if you want Redis, Memcached, or an internal cache.

Example:

```python
import json
import memcache
import lexiredact as vs

mc = memcache.Client(["127.0.0.1:11211"])

pipeline = vs.IngestionPipeline(
    cache_get_func=lambda key: json.loads(mc.get(key)) if mc.get(key) else None,
    cache_set_func=lambda key, value, ttl: mc.set(key, json.dumps(value), time=ttl),
)
```

Available cache hooks:

- `cache_get_func`
- `cache_set_func`
- `cache_connect_func`
- `cache_disconnect_func`
- `cache_delete_func`
- `cache_clear_func`

## 7. Direct Instance Injection

If you already have reusable classes, inject them directly.

```python
import lexiredact as vs
from lexiredact.implementations.cache.memory import MemoryCache

cache = MemoryCache()
embedder = CustomEmbedder(model_name="my-model-v1", dimension=768)
vectorstore = CustomVectorStore()

pipeline = vs.IngestionPipeline(
    cache=cache,
    embedder=embedder,
    vectorstore=vectorstore,
)
```

This approach is usually better than function hooks when:

- your codebase already uses classes
- you want type-checked integration points
- you need more than two or three backend operations

## 8. Minimal End-to-End Example

```python
import asyncio
import lexiredact as vs


class SimpleEmbedder(vs.Embedder):
    async def embed_text(self, text):
        return [0.1, 0.2, 0.3]

    async def embed_batch(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def get_embedding_dimension(self):
        return 3


class SimpleStore(vs.VectorStore):
    async def connect(self):
        pass

    async def close(self):
        pass

    async def add_vectors(self, ids, embeddings, documents, metadata=None):
        print("stored:", ids, documents)

    async def query(self, query_embedding, top_k=5, filter_metadata=None):
        return []

    async def delete(self, ids):
        pass


async def main():
    pipeline = vs.IngestionPipeline(
        embedder=SimpleEmbedder(),
        vectorstore=SimpleStore(),
    )
    await pipeline.initialize()

    doc = vs.Document(
        id="1",
        text="Contact John Doe at john@example.com",
        metadata={"source": "crm"},
    )

    result = await pipeline.process_document(doc)
    print(result.to_dict())

    await pipeline.shutdown()


asyncio.run(main())
```

## 9. Integration Checklist

Before shipping a custom embedder or vector database integration, verify:

- your embedder always returns the same vector length
- your vector store saves sanitized text, not raw text
- your search results return `id`, `document`, `score`, and `metadata`
- your metadata stays JSON-friendly
- your connect and close hooks do not leak resources
- your backend can handle the batch sizes configured in LexiRedact

## 10. Related Examples

See these runnable examples in the repository:

- `examples/custom_embedder.py`
- `examples/custom_vectorstore.py`
