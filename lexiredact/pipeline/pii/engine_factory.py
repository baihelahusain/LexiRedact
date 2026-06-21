"""
pipeline/pii/engine_factory.py — Presidio NLP engine configuration factory.

Encapsulates all NLP engine selection and configuration logic so that
``PIIDetector._ensure_loaded()`` stays simple. Supports the three
Presidio-official NLP engines:

  ``spacy``        — default, fast, works for all supported languages.
  ``transformers`` — HuggingFace NER models; better recall on informal text.
                     Requires: pip install presidio-analyzer[transformers]
  ``stanza``       — Stanford Stanza; strong multilingual support.
                     Requires: pip install presidio-analyzer[stanza]

All failures are raised as ``LexiredactConfigError`` for consistent
error reporting, rather than propagating raw ``ImportError`` or Presidio
exceptions to callers.

Presidio imports are deferred to inside ``build_nlp_engine()`` to avoid
importing the library at module-import time (keeping startup fast when
presidio is not yet initialised).
"""

from __future__ import annotations

from lexiredact.config.schema import PIIConfig


def build_nlp_engine(config: PIIConfig):
    """Build and return a Presidio NlpEngine from PIIConfig.

    Reads ``config.nlp_engine`` and ``config.nlp_model`` to construct the
    appropriate ``NlpEngineProvider`` configuration dict, then calls
    ``provider.create_engine()`` and returns the result.

    Args:
        config: Validated PIIConfig with ``nlp_engine`` and ``nlp_model`` set.
                The ``_resolve_nlp_model`` validator guarantees both are non-empty.

    Returns:
        A Presidio ``NlpEngine`` instance ready to pass into ``AnalyzerEngine``.

    Raises:
        LexiredactConfigError: On missing ``presidio-analyzer`` dependency,
            unsupported engine name, or any engine initialisation failure.
    """
    from lexiredact.exceptions import LexiredactConfigError

    engine_name = config.nlp_engine
    model_name = config.nlp_model
    language = config.language

    # Defer presidio import — keeps module importable without presidio installed.
    try:
        from presidio_analyzer.nlp_engine import NlpEngineProvider  # type: ignore[import-untyped]
    except ImportError as exc:
        raise LexiredactConfigError(
            "presidio-analyzer is required: pip install presidio-analyzer spacy && "
            "python -m spacy download en_core_web_lg",
            context={"error": str(exc)},
        ) from exc

    if engine_name == "spacy":
        nlp_configuration: dict = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": model_name}],
        }
    elif engine_name == "transformers":
        # Requires: pip install presidio-analyzer[transformers]
        nlp_configuration = {
            "nlp_engine_name": "transformers",
            "models": [{"lang_code": language, "model_name": model_name}],
        }
    elif engine_name == "stanza":
        nlp_configuration = {
        "nlp_engine_name": "stanza",
        "models": [{"lang_code": language, "model_name": language}],
    }
    else:
        raise LexiredactConfigError(
            f"Unsupported nlp_engine: '{engine_name}'",
            context={"supported": ["spacy", "transformers", "stanza"], "got": engine_name},
        )

    try:
        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        return provider.create_engine()
    except Exception as exc:
        raise LexiredactConfigError(
            f"Failed to initialise NLP engine '{engine_name}' with model '{model_name}': {exc}",
            context={"nlp_engine": engine_name, "nlp_model": model_name, "language": language},
        ) from exc