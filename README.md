# LexiRedact

LexiRedact is privacy-preserving RAG ingestion middleware. It accepts pre-chunked text, detects and redacts PII, embeds text, and writes sanitized metadata to a vector store.

The package is designed for applications that need a small ingestion layer between user documents and a retrieval system.

## Install

Base package:

```bash
pip install lexiredact
```

Full ingestion stack:

```bash
pip install "lexiredact[all]"
python -m spacy download en_core_web_lg
```

Install only the integrations you need:

```bash
pip install "lexiredact[pii,embed,store,cache,cli]"
```

Optional extras:

- `pii`: Presidio Analyzer, Presidio Anonymizer, spaCy
- `embed`: sentence-transformers
- `store`: ChromaDB
- `cache`: Redis
- `cli`: Click command-line interface
- `all`: all optional integrations

## Quick Start

Create `lexiredact_config.yaml`:

```yaml
pipeline_mode: dual

input_schema:
  id_field: id
  text_field: text
  metadata_fields: [source]

pii:
  entities: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION]
  language: en
  nlp_engine: spacy
  nlp_model: en_core_web_lg
  score_threshold: 0.7

embedder:
  backend: sentence_transformers
  model_name: intfloat/e5-small-v2
  dimension: 384
  document_prefix: "passage: "
  query_prefix: "query: "

store:
  provider: chroma
  collection_name: lexiredact
  persist_directory: ./chroma_db
```

Ingest chunks:

```python
from lexiredact import LexiredactPipeline, load_config

config = load_config("lexiredact_config.yaml")
pipeline = LexiredactPipeline(config)

results = pipeline.ingest(
    [
        {
            "id": "case-001",
            "text": "Jane Doe emailed jane@example.com about the contract.",
            "source": "crm",
        }
    ]
)

for result in results:
    print(result.to_dict())
```

Input must already be chunked. Configure the expected ID, text, and metadata fields with `input_schema`.

## Pipeline Modes

| Mode | Embeds | Stores | Use case |
| --- | --- | --- | --- |
| `dual` | Original text | Sanitized text | Default balance of retrieval quality and sanitized storage metadata |
| `preredacted` | Sanitized text | Sanitized text | Stronger privacy when the embedder must not see PII |
| `raw` | Original text | Original text | Baselines, tests, or non-sensitive data only |

## CLI

Install the CLI extra, then run:

```bash
lexiredact --help
lexiredact validate --config lexiredact_config.yaml --input chunks.json
lexiredact ingest --config lexiredact_config.yaml --input chunks.json --output results.json
lexiredact inspect --config lexiredact_config.yaml --limit 5
lexiredact export --config lexiredact_config.yaml --output export.json
```

`chunks.json` must contain a JSON array of chunk objects.

## Python API

Main imports:

```python
from lexiredact import (
    LexiredactPipeline,
    load_config,
    ProcessingResult,
    DetectedEntity,
)
```

Extension points:

- Pass a custom embedder with `LexiredactPipeline(config, embedder=my_embedder)`.
- Pass a custom vector store with `LexiredactPipeline(config, store=my_store)`.
- Custom embedders implement `lexiredact.pipeline.embedder.base.EmbedderBase`.
- Custom stores implement `lexiredact.pipeline.store.base.VectorStoreBase`.

## Retrieval

LexiRedact handles ingestion. For direct retrieval with the built-in Chroma store:

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

Use `query_embed()` for retrieval queries so query prefixes are applied correctly.

## Docs And Examples

- [Documentation index](docs/index.md)
- [User guide](docs/user_guide.md)
- [Configuration reference](docs/configuration.md)
- [API reference](docs/api.md)
- [CLI guide](docs/cli.md)
- [Examples](examples/)

Useful examples:

- `examples/quickstart.py`
- `examples/custom_embedder.py`
- `examples/custom_vectorstore.py`
- `examples/retrieval_metrics_demo.py`
- `examples/redis_enabled.py`
- `examples/presidio_config_template.py`

## Requirements

- Python 3.10+
- Pydantic 2
- PyYAML
- Optional integrations depending on selected extras

## License

MIT
