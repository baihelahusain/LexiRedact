# CLI

Install the CLI extra:

```bash
pip install "lexiredact[cli,pii,embed,store]"
```

The console command is:

```bash
lexiredact --help
```

## Validate

```bash
lexiredact validate --config lexiredact_config.yaml
lexiredact validate --config lexiredact_config.yaml --input chunks.json
```

Input JSON must be an array of chunk objects.

## Ingest

```bash
lexiredact ingest \
  --config lexiredact_config.yaml \
  --input chunks.json \
  --output results.json \
  --verbose
```

Useful overrides:

```bash
lexiredact ingest --config lexiredact_config.yaml --input chunks.json --mode preredacted
lexiredact ingest --config lexiredact_config.yaml --input chunks.json --batch-size 8
```

## Inspect

```bash
lexiredact inspect --config lexiredact_config.yaml --limit 10
```

Prints collection metadata and sample stored chunks.

## Stats

```bash
lexiredact stats --config lexiredact_config.yaml
```

Shows collection count, embedding dimension, and text-length statistics.

## Export

```bash
lexiredact export --config lexiredact_config.yaml --output export.json
```

Exports stored chunk IDs, text metadata, and metadata fields.

## Info

```bash
lexiredact info --config lexiredact_config.yaml
```

Prints the active configuration without loading the ML model.
