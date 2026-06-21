# Privacy Model

LexiRedact has three ingestion modes.

## `dual`

Flow:

```text
detect PII -> run redaction and original-text embedding concurrently -> store sanitized text
```

The vector is generated from original text, while vector-store metadata receives sanitized text. This is the default mode because it balances retrieval quality with reduced metadata exposure.

Use `dual` when retrieval quality matters and your privacy policy allows original text to be processed by the embedding model.

## `preredacted`

Flow:

```text
detect PII -> redact text -> embed sanitized text -> store sanitized text
```

The embedding model sees redacted text. This is stricter than `dual`, but retrieval quality can drop when PII tokens were semantically useful.

Use `preredacted` when PII must not enter the embedding model.

## `raw`

Flow:

```text
embed original text -> store original text
```

No detection or redaction runs. Use this only for evaluation baselines, tests, or data that is already safe.

## Stored metadata

In `dual` and `preredacted`, the store receives metadata like:

```python
{"text": sanitized_text, **configured_metadata_fields}
```

Be careful with `metadata_fields`; those values are copied as-is.

## Redaction format

PII spans are replaced with placeholders such as:

```text
<PERSON>
<EMAIL_ADDRESS>
<PHONE_NUMBER>
```

The entity types come from the detected Presidio labels.
