"""
config/schema.py — Pydantic v2 configuration models for lexiredact.

All models use extra="forbid" so unknown YAML keys are rejected at startup.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class InputSchemaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_field: str = "text"
    id_field: str = "id"
    metadata_fields: list[str] = []


class PIIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[str] = [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "CREDIT_CARD",
        "IBAN_CODE",
        "IP_ADDRESS",
    ]
    language: str = "en"

    # NLP engine selection (new authoritative fields)
    nlp_engine: Literal["spacy", "transformers", "stanza"] = "spacy"
    nlp_model: str = ""  # resolved by validator below; empty string triggers default resolution

    # Deprecated: use nlp_model instead. Kept for backward compatibility with existing YAML configs.
    spacy_model: str = "en_core_web_lg"

    score_threshold: float = 0.7
    batch_size: int = 16

    @model_validator(mode="after")
    def _resolve_nlp_model(self) -> "PIIConfig":
        if self.nlp_model == "":
            if self.nlp_engine == "spacy":
                object.__setattr__(self, "nlp_model", self.spacy_model)
            else:
                raise ValueError(
                    f"nlp_model must be set explicitly when nlp_engine='{self.nlp_engine}'. "
                    f"Example for transformers: nlp_model='dslim/bert-base-NER'"
                )
        return self


class EmbedderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Backend selection
    backend: Literal["sentence_transformers", "huggingface"] = "sentence_transformers"

    model_name: str = "intfloat/e5-small-v2"
    batch_size: int = 32
    device: str = "cpu"
    normalize_embeddings: bool = True

    # Prefix fields — config-driven rather than hardcoded
    document_prefix: str = "passage: "  # prepended to each text during ingestion
    query_prefix: str = "query: "        # prepended to each text during retrieval

    # Dimension override — None means auto-detect from model after load.
    # Set explicitly to avoid model load during ChromaStore construction.
    dimension: int | None = None


class CacheConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    redis_url: str = "redis://localhost:6379"
    ttl_seconds: int = 86400
    key_prefix: str = "vs"


class StoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "chroma"
    collection_name: str = "lexiredact"
    persist_directory: str = "./chroma_db"


class LexiredactConfig(BaseModel):
    """Root configuration object for the entire LexiRedact pipeline.

    pipeline_mode:
        "raw"         — embed and store original text; skip PII entirely.
        "preredacted" — detect → redact → embed sanitised text (sequential).
        "dual"        — embed original, store sanitised in parallel (default).
    """

    model_config = ConfigDict(extra="forbid")

    pipeline_mode: Literal["raw", "preredacted", "dual"] = "dual"
    input_schema: InputSchemaConfig = InputSchemaConfig()
    pii: PIIConfig = PIIConfig()
    embedder: EmbedderConfig = EmbedderConfig()
    cache: CacheConfig = CacheConfig()
    store: StoreConfig = StoreConfig()