"""
PII redaction with placeholder substitution.

Replaces detected PII entities with configurable placeholders.
Preserves sentence structure and context for embedding quality.
"""
from typing import List, Tuple, Dict, Any, Optional
import asyncio
from presidio_analyzer import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class PIIRedactor:
    """
    Redacts PII by replacing entities with placeholders.

    Default format: <ENTITY_TYPE> (e.g., <PERSON>, <PHONE_NUMBER>)
    This preserves context and sentence structure for embeddings.
    """

    def __init__(
        self,
        operator_map: Optional[Dict[str, Dict[str, Any]]] = None,
        default_replacement: str = "<{entity_type}>",
    ):
        """Initialize redaction engine."""
        self.anonymizer = AnonymizerEngine()
        self.operator_map = operator_map or {}
        self.default_replacement = default_replacement

    async def redact(
        self,
        text: str,
        detection_results: List[RecognizerResult]
    ) -> Tuple[str, List[str]]:
        """
        Redact PII entities in text with placeholders.

        Args:
            text: Original text
            detection_results: List of detected PII entities

        Returns:
            Tuple of (redacted_text, list_of_entity_types_found)
        """
        if not detection_results:
            return text, []

        entity_types = sorted(set(r.entity_type for r in detection_results))

        operators = {}
        for entity_type in entity_types:
            operator_config = self.operator_map.get(entity_type)
            if operator_config:
                operators[entity_type] = OperatorConfig(
                    operator_name=operator_config.get("operator", "replace"),
                    params=operator_config.get("params", {}),
                )
                continue

            operators[entity_type] = OperatorConfig(
                "replace",
                {"new_value": self.create_placeholder(entity_type)},
            )

        loop = asyncio.get_event_loop()
        anonymized = await loop.run_in_executor(
            None,
            lambda: self.anonymizer.anonymize(
                text=text,
                analyzer_results=detection_results,
                operators=operators,
            ),
        )

        return anonymized.text, entity_types

    async def redact_batch(
        self,
        texts: List[str],
        detection_results: List[List[RecognizerResult]]
    ) -> List[Tuple[str, List[str]]]:
        """
        Redact PII in multiple texts concurrently.

        Args:
            texts: List of original texts
            detection_results: List of detection results for each text

        Returns:
            List of (redacted_text, entity_types) tuples
        """
        tasks = [
            self.redact(text, results)
            for text, results in zip(texts, detection_results)
        ]
        return await asyncio.gather(*tasks)

    def create_placeholder(self, entity_type: str) -> str:
        """
        Create placeholder for an entity type.

        Args:
            entity_type: Entity type (e.g., "PERSON")

        Returns:
            Placeholder string (e.g., "<PERSON>")
        """
        return self.default_replacement.replace("{entity_type}", entity_type)
