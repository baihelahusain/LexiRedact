# Configuration Reference

This document describes all available configuration keys, their types, default values, and behavior.

---

## Configuration Table

| Key | Type | Default | Description |
|----|----|----|----|
| `cache_backend` | `str` | `"memory"` | Cache implementation: `memory`, `redis`, `none` |
| `cache_ttl` | `int` | `3600` | Cache TTL in seconds |
| `redis_host` | `str` | `"localhost"` | Redis hostname |
| `redis_port` | `int` | `6379` | Redis port |
| `redis_db` | `int` | `0` | Redis database index |
| `embedding_model` | `str` | `"BAAI/bge-small-en-v1.5"` | FastEmbed model name |
| `embedding_batch_size` | `int` | `32` | Batch size for `embed_batch` calls |
| `vectorstore_backend` | `str` | `"chroma"` | Vector store: `chroma` or `custom` |
| `vectorstore_path` | `str` | `"./lexiredact_data"` | ChromaDB persistence directory |
| `vectorstore_collection` | `str` | `"documents"` | ChromaDB collection name |
| `parallel_processing` | `bool` | `True` | Run PII detection and embedding in parallel |
| `max_batch_size` | `int` | `1000` | Maximum documents per `process_batch` call |
| `pii_entities` | `list[str]` | See below | Presidio entity types to detect |
| `presidio_language` | `str` | `"en"` | Language passed to Presidio analyzer |
| `presidio_score_threshold` | `float` | `0.0` | Minimum Presidio confidence score to keep |
| `presidio_allow_list` | `list[str]` | `[]` | Values or patterns to skip during detection |
| `presidio_allow_list_match` | `str` | `"exact"` | Allow-list mode: `exact` or `regex` |
| `presidio_custom_patterns` | `list[dict]` | `[]` | Custom regex recognizers to register |
| `presidio_operator_map` | `dict` | `{}` | Per-entity anonymizer operator settings |
| `presidio_default_replacement` | `str` | `"<{entity_type}>"` | Fallback replacement template; supports `{entity_type}` |
| `tracking_enabled` | `bool` | `False` | Enable experiment tracking |
| `tracking_backend` | `str` | `"none"` | Tracker: `mlflow` or `none` |
| `mlflow_tracking_uri` | `str` | `"http://localhost:5000"` | MLflow server URI |
| `mlflow_experiment_name` | `str` | `"lexiredact"` | MLflow experiment name |
| `mlflow_run_name` | `str \| null` | `None` | Optional run name shown in the MLflow UI |
| `mlflow_log_artifacts` | `bool` | `True` | Log a JSON summary artifact for each run |
| `mlflow_log_storage_samples` | `int` | `5` | Number of stored records to include in the MLflow artifact sample |
| `timeout_seconds` | `int` | `30` | Per-document processing timeout |

---

## Default PII Entities

```python
[
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "US_SSN",
    "LOCATION",
    "DATE_TIME",
    "MEDICAL_LICENSE",
    "US_PASSPORT"
]
```

---

## Example Configuration

```yaml
cache_backend: memory
cache_ttl: 3600
embedding_model: BAAI/bge-small-en-v1.5
vectorstore_backend: chroma
vectorstore_path: ./lexiredact_data
parallel_processing: true
pii_entities:
  - PERSON
  - EMAIL_ADDRESS
  - PHONE_NUMBER
presidio_language: en
presidio_score_threshold: 0.55
presidio_allow_list:
  - LexiRedact
presidio_allow_list_match: exact
presidio_custom_patterns:
  - entity_name: EMPLOYEE_ID
    regex_pattern: "\\bEMP\\d{6}\\b"
    score: 0.85
presidio_operator_map:
  PERSON:
    operator: replace
    params:
      new_value: "<PERSON>"
  EMPLOYEE_ID:
    operator: replace
    params:
      new_value: "<EMPLOYEE_ID>"
presidio_default_replacement: "<{entity_type}>"
tracking_enabled: false
tracking_backend: none
mlflow_tracking_uri: http://localhost:5000
mlflow_experiment_name: lexiredact
mlflow_run_name: null
mlflow_log_artifacts: true
mlflow_log_storage_samples: 5
timeout_seconds: 30
```
