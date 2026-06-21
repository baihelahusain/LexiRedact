"""Generate common PII configuration dictionaries."""

from __future__ import annotations

from pprint import pprint

from _bootstrap import ROOT  # noqa: F401

from lexiredact import load_config


spacy_config = {
    "pii": {
        "entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"],
        "language": "en",
        "nlp_engine": "spacy",
        "nlp_model": "en_core_web_lg",
        "score_threshold": 0.7,
        "batch_size": 16,
    }
}

transformers_config = {
    "pii": {
        "entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"],
        "language": "en",
        "nlp_engine": "transformers",
        "nlp_model": "dslim/bert-base-NER",
        "score_threshold": 0.6,
        "batch_size": 8,
    }
}

pprint(load_config(spacy_config).pii.model_dump())
pprint(load_config(transformers_config).pii.model_dump())
