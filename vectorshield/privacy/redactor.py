"""
PII redaction with placeholder substitution.

Replaces detected PII entities with type-specific placeholders.
Preserves sentence structure and context for embedding quality.
"""
from typing import List, Tuple
import asyncio
from presidio_analyzer import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class PIIRedactor:
    """
    Redacts PII by replacing entities with placeholders.
    
    Uses format: <ENTITY_TYPE> (e.g., <PERSON>, <PHONE_NUMBER>)
    This preserves context and sentence structure for embeddings.
    """
    
    def __init__(self):
        """Initialize redaction engine."""
        self.anonymizer = AnonymizerEngine()
    
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
            
        Example:
            >>> from presidio_analyzer import RecognizerResult
            >>> redactor = PIIRedactor()
            >>> results = [
            ...     RecognizerResult(entity_type="PERSON", start=5, end=9, score=0.9),
            ...     RecognizerResult(entity_type="PHONE_NUMBER", start=13, end=21, score=0.95)
            ... ]
            >>> text = "Call John at 555-0199"
            >>> clean, entities = await redactor.redact(text, results)
            >>> print(clean)
            "Call <PERSON> at <PHONE_NUMBER>"
            >>> print(entities)
            ["PERSON", "PHONE_NUMBER"]
        """
        if not detection_results:
            return text, []
        
        # Extract entity types
        entity_types = sorted(set(r.entity_type for r in detection_results))
        
        # Configure anonymizer to use placeholders
        operators = {
            entity_type: OperatorConfig("replace", {"new_value": f"<{entity_type}>"})
            for entity_type in entity_types
        }
        
        loop = asyncio.get_event_loop()
        
        # Anonymize text
        anonymized = await loop.run_in_executor(
            None,
            lambda: self.anonymizer.anonymize(
                text=text,
                analyzer_results=detection_results,
                operators=operators
            )
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
        return f"<{entity_type}>"