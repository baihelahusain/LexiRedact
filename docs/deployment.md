# Deployment

## Install dependencies

For a complete local deployment:

```bash
pip install "lexiredact[all]"
python -m spacy download en_core_web_lg
```

For production images, install only the extras you use.

## Persist vector data

Set a durable Chroma directory:

```yaml
store:
  provider: chroma
  collection_name: lexiredact_prod
  persist_directory: /data/chroma
```

Back up this directory according to your retention policy.

## Model startup

Set `embedder.dimension` when known. This avoids loading the embedding model during store construction.

```yaml
embedder:
  model_name: intfloat/e5-small-v2
  dimension: 384
```

## Redis

Use Redis when repeated exact chunks are common:

```yaml
cache:
  enabled: true
  redis_url: redis://redis:6379
```

Cache failure does not fail ingestion.

## Operational checks

- Run `lexiredact validate` before deploying config changes.
- Keep `pipeline_mode` set to `dual` or `preredacted` for sensitive data.
- Monitor storage failures; they are raised to the caller.
- Keep `metadata_fields` minimal.
- Use versioned configs so pipeline behavior is auditable.
