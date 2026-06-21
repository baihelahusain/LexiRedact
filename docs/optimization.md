# Optimization

## Avoid startup model loads

Set `embedder.dimension` when you know the model dimension:

```yaml
embedder:
  model_name: intfloat/e5-small-v2
  dimension: 384
```

## Batch sizes

Tune:

- `pii.batch_size`
- `embedder.batch_size`

Larger batches can improve throughput but increase memory use.

## Prefixes

Use the correct prefixes for asymmetric embedding models:

```yaml
document_prefix: "passage: "
query_prefix: "query: "
```

For models without required prefixes, use empty strings.

## Redis cache

Enable cache when exact text repeats:

```yaml
cache:
  enabled: true
```

Cache helps `raw` and `dual` modes. It is less useful in `preredacted` mode because sanitized text can differ from the original text cache key path.

## Mode choice

- Use `dual` for strong retrieval quality with sanitized storage metadata.
- Use `preredacted` when the embedder must not see PII.
- Use `raw` only for non-sensitive baselines.
