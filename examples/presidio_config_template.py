"""
Presidio configuration template for LexiRedact.

Shows how to control Presidio behavior from config.
"""
import asyncio
from pathlib import Path

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs


def build_config() -> dict:
    """Create a config with custom Presidio parameters."""
    return vs.load_config(
        config_dict={
            "pii_entities": [
                "PERSON",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "US_SSN",
                "EMPLOYEE_ID",
            ],
            "presidio_language": "en",
            "presidio_score_threshold": 0.55,
            "presidio_allow_list": [
                "LexiRedact",
                "support@company.internal",
            ],
            "presidio_allow_list_match": "exact",
            "presidio_custom_patterns": [
                {
                    "entity_name": "EMPLOYEE_ID",
                    "regex_pattern": r"\bEMP\d{6}\b",
                    "score": 0.85,
                }
            ],
            "presidio_operator_map": {
                "PERSON": {
                    "operator": "replace",
                    "params": {"new_value": "<PERSON>"},
                },
                "EMAIL_ADDRESS": {
                    "operator": "replace",
                    "params": {"new_value": "<EMAIL>"},
                },
                "EMPLOYEE_ID": {
                    "operator": "replace",
                    "params": {"new_value": "<EMPLOYEE_ID>"},
                },
            },
            "presidio_default_replacement": "<{entity_type}>",
        }
    )


async def run_with_config(config: dict, document_id: str, text: str) -> None:
    """Run a document through the pipeline with the provided config."""
    pipeline_config = dict(config)
    pipeline_config.update(
        {
            "vectorstore_path": str(Path(".tmp-build") / "presidio_config_data"),
            "vectorstore_collection": f"presidio_{document_id}",
            "mlflow_log_artifacts": False,
        }
    )

    pipeline = vs.IngestionPipeline(config=pipeline_config)
    await pipeline.initialize()

    result = await pipeline.process_document(
        vs.Document(
            id=document_id,
            text=text,
            metadata={"source": "presidio_config_template"},
        )
    )
    print(result.to_dict())

    await pipeline.shutdown()


async def main() -> None:
    print("Inline config example:")
    await run_with_config(
        config=build_config(),
        document_id="inline-config",
        text=(
            "John Smith can be reached at john.smith@example.com or 555-123-4567. "
            "His employee ID is EMP123456 and LexiRedact should stay visible."
        ),
    )

    yaml_path = Path(__file__).with_name("presidio_config_template.yaml")
    print()
    print(f"YAML template path: {yaml_path}")

    print("YAML config example:")
    await run_with_config(
        config=vs.load_config(config_file=str(yaml_path)),
        document_id="yaml-config",
        text="Alice Brown has employee ID EMP654321 and email alice@example.com.",
    )


if __name__ == "__main__":
    asyncio.run(main())
