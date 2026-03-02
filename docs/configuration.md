# Configuration Reference

VectorShield configuration can be loaded from:

- default values (`load_config()`)
- Python dict (`load_config(config_dict=...)`)
- YAML file (`load_config(config_file="config.yaml")`)

`load_config` merges values in this order:
1. defaults
2. YAML file
3. `config_dict` overrides

## Example YAML

```yaml
pii_entities:
  - PERSON
  - PHONE_NUMBER
  - EMAIL_ADDRESS

embedding_model: BAAI/bge-small-en-v1.5
embedding_batch_size: 32

cache_backend: redis
cache_ttl: 3600
redis_host: localhost
redis_port: 6379
redis_db: 0

vectorstore_backend: chroma
vectorstore_path: ./vectorshield_data
vectorstore_collection: documents

parallel_processing: true
max_batch_size: 1000

tracking_enabled: false
tracking_backend: none
mlflow_tracking_uri: http://localhost:5000
mlflow_experiment_name: vectorshield

enable_async: true
timeout_seconds: 30
```

## Key Settings

- `pii_entities`
  - PII label list used by detector.
- `embedding_model`
  - Model passed to built-in FastEmbed backend.
- `cache_backend`
  - `memory`, `redis`, or `none`.
- `cache_ttl`
  - Cache expiration in seconds.
- `vectorstore_backend`
  - `chroma` (built-in) or custom via injection.
- `vectorstore_path`
  - Local persistence directory for Chroma.
- `parallel_processing`
  - Runs PII detection and embedding concurrently on cache miss.
- `max_batch_size`
  - Max documents accepted by `process_batch`.
- `tracking_enabled`
  - Enables tracker backend.

## Validation Rules

Current validation checks include:

- `cache_ttl >= 0`
- `max_batch_size >= 1`
- `embedding_batch_size >= 1`
- supported values for:
  - `cache_backend`
  - `vectorstore_backend`
  - `tracking_backend`

## Python Usage

```python
import vectorshield as vs

config = vs.load_config(config_dict={
    "cache_backend": "redis",
    "redis_host": "localhost",
    "parallel_processing": True
})

pipeline = vs.IngestionPipeline(config=config)
```
