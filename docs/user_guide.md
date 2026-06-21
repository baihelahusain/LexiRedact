# User Guide

## Install

Base install contains configuration models and the public package imports:

```bash
pip install lexiredact
```

For the full ingestion pipeline, install the optional dependencies used by the current implementation:

```bash
pip install "lexiredact[all]"
python -m spacy download en_core_web_lg
```

Use narrower extras when you know what you need:

```bash
pip install "lexiredact[pii,embed,store,cli]"
```

## Minimal config

```yaml
pipeline_mode: dual

input_schema:
  id_field: id
  text_field: text
  metadata_fields: [source]

pii:
  entities: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, CREDIT_CARD, IBAN_CODE, IP_ADDRESS]
  language: en
  nlp_engine: spacy
  nlp_model: en_core_web_lg
  score_threshold: 0.7
  batch_size: 16

embedder:
  backend: sentence_transformers
  model_name: intfloat/e5-small-v2
  batch_size: 32
  device: cpu
  normalize_embeddings: true
  document_prefix: "passage: "
  query_prefix: "query: "
  dimension: 384

cache:
  enabled: false

store:
  provider: chroma
  collection_name: lexiredact
  persist_directory: ./chroma_db
```

Setting `embedder.dimension` avoids loading the embedding model just to initialize Chroma.

## Python ingestion

```python
from lexiredact import LexiredactPipeline, load_config

config = load_config("lexiredact_config.yaml")
pipeline = LexiredactPipeline(config)

chunks = [
    {
        "id": "case-001",
        "text": "Jane Doe emailed jane@example.com about the contract.",
        "source": "crm",
    }
]

results = pipeline.ingest(chunks)

for result in results:
    print(result.to_dict())
```

`ingest()` expects a list of dictionaries. The ID and text fields are controlled by `input_schema.id_field` and `input_schema.text_field`. Fields listed in `metadata_fields` are copied to vector-store metadata.

Invalid chunks are skipped with warnings. Storage errors are raised to the caller.

## CLI ingestion

Create `chunks.json`:

```json
[
  {
    "id": "case-001",
    "text": "Jane Doe emailed jane@example.com about the contract.",
    "source": "crm"
  }
]
```

Run:

```bash
lexiredact validate --config lexiredact_config.yaml --input chunks.json
lexiredact ingest --config lexiredact_config.yaml --input chunks.json --output results.json
```

Inspect or export stored chunks:

```bash
lexiredact info --config lexiredact_config.yaml
lexiredact inspect --config lexiredact_config.yaml --limit 5
lexiredact stats --config lexiredact_config.yaml
lexiredact export --config lexiredact_config.yaml --output export.json
```

## Retrieval

LexiRedact ingestion stores vectors and sanitized text. For direct Chroma retrieval, create the same embedder and store, embed the query with `query_embed()`, and call `store.query()`:

```python
from lexiredact import load_config
from lexiredact.pipeline.embedder.registry import create_embedder
from lexiredact.pipeline.store.chroma import ChromaStore

config = load_config("lexiredact_config.yaml")
embedder = create_embedder(config.embedder)
store = ChromaStore(config.store, embedder.get_dimension())

query_vector = embedder.query_embed(["contract email"])[0]
matches = store.query(query_vector, top_k=3)
```

Use `query_prefix` for query embeddings. Do not call `embed_batch()` for retrieval queries when using asymmetric models such as E5.

## Pipeline modes

- `dual`: detects PII, embeds original text, stores sanitized text. This keeps retrieval quality high while keeping original text out of the vector store metadata.
- `preredacted`: detects and redacts PII before embedding. This gives the strongest embedding-time privacy at some retrieval-quality cost.
- `raw`: skips PII detection and stores original text. Use it only for baselines, tests, or non-sensitive data.

## Production checklist

- Use `dual` or `preredacted` for sensitive data.
- Keep `raw` out of production privacy-sensitive flows.
- Pin `embedder.dimension` when using Chroma to avoid startup downloads.
- Set `metadata_fields` deliberately; metadata is stored with chunks.
- Use Redis cache only when repeated exact-text embeddings are common.
- Validate config and input before ingestion.
- Treat storage errors as failed ingestion and retry intentionally.
