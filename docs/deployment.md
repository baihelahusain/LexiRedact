# Deployment Checklist

This checklist helps prepare VectorShield for production use.

## 1. Packaging and Release

- Confirm package metadata is correct in `pyproject.toml`.
- Build package:
  - `python -m build`
- Validate metadata:
  - `python -m twine check dist/*`
- Ensure CI workflow passes:
  - `.github/workflows/package-check.yml`

## 2. Runtime Dependencies

- Install base package:
  - `pip install vectorshield`
- Optional extras:
  - Redis: `pip install vectorshield[redis]`
  - MLflow: `pip install vectorshield[mlflow]`

## 3. Infrastructure

- Cache:
  - Use Redis for shared caching across multiple instances.
- Vector store:
  - Configure durable storage path for Chroma.
- Tracker:
  - Keep disabled unless explicitly required.

## 4. Security

- Restrict network access between app, cache, and DB.
- Enforce TLS where available.
- Avoid logging raw request text in production logs.
- Treat embeddings and metadata as sensitive data.

## 5. Configuration

- Set explicit environment-specific config:
  - cache backend + TTL
  - vector store path/collection
  - batch limits and timeouts
- Keep `parallel_processing=true` unless debugging.

## 6. Validation Before Go-Live

- Smoke test:
  - initialize
  - process single document
  - process batch
  - shutdown
- Confirm stored documents are redacted.
- Confirm monitoring/alerts for latency and failures.

## 7. Recommended First Production Config

```yaml
cache_backend: redis
cache_ttl: 3600
parallel_processing: true
vectorstore_backend: chroma
vectorstore_path: /var/lib/vectorshield
tracking_enabled: false
max_batch_size: 1000
timeout_seconds: 30
```
