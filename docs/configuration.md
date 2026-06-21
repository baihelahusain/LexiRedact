# Configuration

Load configuration from YAML, `pathlib.Path`, string path, or dictionary:

```python
from lexiredact import load_config

config = load_config("lexiredact_config.yaml")
```

Unknown keys are rejected. Validation failures raise `LexiredactConfigError`.

## Full reference

```yaml
pipeline_mode: dual

input_schema:
  text_field: text
  id_field: id
  metadata_fields: []

pii:
  entities:
    - PERSON
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - LOCATION
    - CREDIT_CARD
    - IBAN_CODE
    - IP_ADDRESS
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
  dimension: null

cache:
  enabled: false
  redis_url: redis://localhost:6379
  ttl_seconds: 86400
  key_prefix: vs

store:
  provider: chroma
  collection_name: lexiredact
  persist_directory: ./chroma_db
```

## Root

`pipeline_mode` accepts:

- `dual`: detect PII, embed original text, store sanitized text.
- `preredacted`: detect PII, redact text, embed sanitized text, store sanitized text.
- `raw`: embed and store original text. Use for baselines only.

## Input schema

`input_schema.id_field` and `input_schema.text_field` define the required keys in each input dictionary. `metadata_fields` controls which extra keys are copied into vector-store metadata.

Example:

```yaml
input_schema:
  id_field: doc_id
  text_field: body
  metadata_fields: [tenant_id, source, created_at]
```

Then each input item must include `doc_id` and `body`.

## PII

`nlp_engine` accepts `spacy`, `transformers`, or `stanza`.

For the default spaCy path:

```bash
pip install "lexiredact[pii]"
python -m spacy download en_core_web_lg
```

For transformers or stanza, set `nlp_model` explicitly:

```yaml
pii:
  nlp_engine: transformers
  nlp_model: dslim/bert-base-NER
```

`spacy_model` remains accepted for backward compatibility, but new configs should use `nlp_model`.

## Embedder

Supported backends:

- `sentence_transformers`: requires `lexiredact[embed]`.
- `huggingface`: requires `transformers` and `torch`.

For E5-style models, keep:

```yaml
document_prefix: "passage: "
query_prefix: "query: "
```

For models that do not require prefixes, set both to empty strings.

`dimension` can be set to avoid model loading during store initialization.

## Cache

When `cache.enabled` is `true`, Redis is used for exact-text embedding cache hits in `raw` and `dual` modes. Cache failures are logged and treated as misses.

```yaml
cache:
  enabled: true
  redis_url: redis://localhost:6379
  ttl_seconds: 86400
  key_prefix: lexiredact
```

## Store

The built-in store is Chroma:

```yaml
store:
  provider: chroma
  collection_name: lexiredact
  persist_directory: ./chroma_db
```

Use `LexiredactPipeline(config, store=my_store)` to provide another vector store.
