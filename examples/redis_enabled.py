"""Enable Redis embedding cache in configuration.

Run Redis locally before using this with a real pipeline:
    docker run --rm -p 6379:6379 redis:7
"""

from __future__ import annotations

from _bootstrap import ROOT  # noqa: F401

from lexiredact import load_config


config = load_config(
    {
        "pipeline_mode": "dual",
        "cache": {
            "enabled": True,
            "redis_url": "redis://localhost:6379",
            "ttl_seconds": 3600,
            "key_prefix": "lexiredact-demo",
        },
        "embedder": {"dimension": 384},
    }
)

print(config.cache)
print("Cache failures are treated as misses, so ingestion can continue if Redis is down.")
