# LexiRedact

LexiRedact is a privacy-preserving RAG ingestion middleware package for detecting and redacting PII before content is embedded and written to a vector store.

## Installation

```bash
pip install lexiredact
```

Optional dependency groups are available for specific integrations:

```bash
pip install "lexiredact[pii,embed,store,cache,cli]"
```

## Quick Start

```python
from lexiredact import LexiredactPipeline, load_config

config = load_config("lexiredact_config.yaml")
pipeline = LexiredactPipeline(config)
```

## CLI

```bash
lexiredact --help
```

## Release

This project publishes to PyPI from GitHub Actions when a version tag is pushed:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The PyPI project must be configured for Trusted Publishing with the `pypi` environment and the `.github/workflows/publish.yml` workflow.
