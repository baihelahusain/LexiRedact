# Chunking

LexiRedact expects pre-chunked input. It does not split documents for you.

Each chunk is a dictionary with an ID field, a text field, and optional metadata fields:

```python
[
    {
        "id": "doc-1:p1",
        "text": "Jane Doe signed the agreement.",
        "source": "contract.pdf",
        "page": 1,
    }
]
```

Configure field names:

```yaml
input_schema:
  id_field: id
  text_field: text
  metadata_fields: [source, page]
```

## Validation

Each valid chunk must include:

- the configured ID field
- the configured text field
- non-empty text after trimming whitespace

Invalid chunks are skipped during `ingest()` and logged as warnings.

## Chunking recommendations

- Keep chunks large enough to preserve context.
- Keep chunks small enough for your embedding model and retrieval strategy.
- Use stable IDs so repeated ingestion updates the same vector-store records.
- Put routing metadata such as tenant, source, or document type in `metadata_fields`.
- Do not put sensitive raw PII in metadata fields.

## Example IDs

```text
contract-42:p001
ticket-9001:comment-003
user-guide:v2:section-05
```

Stable IDs make Chroma upserts idempotent.
