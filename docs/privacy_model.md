# Privacy Model

## Objective

LexiRedact is designed to minimize exposure of personally identifiable information (PII)
while still enabling high-quality vector search.

## Core Strategy: Embed Original, Store Sanitized

The pipeline separates semantic quality from storage privacy:

- Embeddings are generated from original text.
- Stored documents are redacted text only.

This prevents sensitive raw content from being written into the vector database while
avoiding quality loss that usually occurs when embeddings are computed from aggressively redacted text.

## PII Entity Coverage

Default configured entities include:

- `PERSON`
- `PHONE_NUMBER`
- `EMAIL_ADDRESS`
- `CREDIT_CARD`
- `US_SSN`
- `LOCATION`
- `DATE_TIME`
- `MEDICAL_LICENSE`
- `US_PASSPORT`

You can override this using config.

## Redaction Behavior

Detected entities are replaced with type placeholders in sanitized output, for example:

- `john@example.com` -> `<EMAIL_ADDRESS>`
- `555-123-4567` -> `<PHONE_NUMBER>`

Sanitized text is what gets persisted to the vector store.

## Caching Model

Cache entries store:

- `clean_text`
- `pii_found`

Cache keys are derived from original text hashes via `generate_cache_key`.

Implications:

- Repeated text avoids repeat PII detection.
- Lower latency for duplicate or recurring content.
- Better horizontal scaling with Redis in distributed deployments.

## Trust Boundaries

- Application runtime:
  - Sees original content during processing.
- Cache backend:
  - Sees sanitized output + PII labels.
- Vector store:
  - Sees sanitized text, embeddings, and metadata.
- Tracker:
  - Receives aggregate metrics and params.
  - Avoid sending raw PII in tracker metadata.

## Operational Controls

For production, recommended controls:

- Set strict network access between services.
- Encrypt storage and transport channels.
- Restrict logs to avoid raw payload output.
- Configure retention for cache/vector DB/tracker.
- Keep `tracking_enabled=false` unless observability is needed.

## Residual Risks

Vector representations can still encode semantic information from original text.
Treat embeddings as sensitive artifacts and secure vector storage appropriately.

Also review metadata handling, since metadata may contain identifiers if supplied upstream.
