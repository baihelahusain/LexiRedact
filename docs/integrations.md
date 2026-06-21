# Integrations

## Presidio

PII detection uses Presidio Analyzer. Redaction uses Presidio Anonymizer.

Default setup:

```bash
pip install "lexiredact[pii]"
python -m spacy download en_core_web_lg
```

Config:

```yaml
pii:
  language: en
  nlp_engine: spacy
  nlp_model: en_core_web_lg
  entities: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER]
```

For transformers:

```yaml
pii:
  nlp_engine: transformers
  nlp_model: dslim/bert-base-NER
```

## Embeddings

Sentence Transformers:

```bash
pip install "lexiredact[embed]"
```

```yaml
embedder:
  backend: sentence_transformers
  model_name: intfloat/e5-small-v2
  dimension: 384
  document_prefix: "passage: "
  query_prefix: "query: "
```

Hugging Face AutoModel:

```bash
pip install transformers torch
```

```yaml
embedder:
  backend: huggingface
  model_name: sentence-transformers/all-MiniLM-L6-v2
  document_prefix: ""
  query_prefix: ""
```

## Chroma

Install:

```bash
pip install "lexiredact[store]"
```

Config:

```yaml
store:
  provider: chroma
  collection_name: lexiredact
  persist_directory: ./chroma_db
```

The built-in Chroma store uses persistent local storage and cosine distance.

## Redis

Install:

```bash
pip install "lexiredact[cache]"
```

Config:

```yaml
cache:
  enabled: true
  redis_url: redis://localhost:6379
  ttl_seconds: 86400
  key_prefix: lexiredact
```

The cache is transparent. If Redis is unavailable, LexiRedact logs a warning and computes embeddings normally.

## Custom embedder

Pass an `EmbedderBase` implementation to `LexiredactPipeline`.

See `examples/custom_embedder.py`.

## Custom vector store

Pass a `VectorStoreBase` implementation to `LexiredactPipeline`.

See `examples/custom_vectorstore.py`.
