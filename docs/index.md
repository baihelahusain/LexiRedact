# LexiRedact Documentation

LexiRedact is privacy-preserving ingestion middleware for RAG pipelines. It accepts pre-chunked text, optionally detects and redacts PII, embeds the selected text, and writes sanitized metadata to a vector store.

## Start here

- [User guide](user_guide.md): installation, first ingestion, and retrieval.
- [Configuration](configuration.md): every supported YAML field.
- [API](api.md): public Python API and extension points.
- [CLI](cli.md): command-line workflows.
- [Privacy model](privacy_model.md): how `raw`, `preredacted`, and `dual` modes differ.
- [Integrations](integrations.md): custom embedders, vector stores, Redis, Chroma, and Presidio.

## Examples

The `examples/` folder contains runnable scripts for quick start, custom embedders, custom vector stores, Redis configuration, Presidio configuration, and retrieval metrics.
