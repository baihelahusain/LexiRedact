# CLI Usage

LexiRedact installs a `lexiredact` command.

## Commands

- `lexiredact version`
- `lexiredact process`

## Show Version

```bash
lexiredact version
```

## Process Documents

Input JSON shape:

```json
{
  "documents": [
    {"id": "1", "text": "Call John at 555-123-4567", "metadata": {"source": "crm"}}
  ]
}
```

Run from file:

```bash
lexiredact process -i input.json -o output.json
```

Run from stdin:

```bash
cat input.json | lexiredact process -i -
```

Use config file:

```bash
lexiredact process -i input.json -o output.json -c config.yaml
```

Show stats on stderr:

```bash
lexiredact process -i input.json --stats
```

## Output

`process` outputs batch-level summary:

- `batch_id`
- `total_processed`
- `total_time_seconds`
- `results[]`

Each result includes:

- `id`
- `status`
- `original_preview`
- `clean_text`
- `pii_found`
- `vector_preview`
- `metadata`
