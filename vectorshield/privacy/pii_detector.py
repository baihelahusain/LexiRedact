"""
PII detection using Microsoft Presidio.

Detects personally identifiable information in text without modifying it.
"""
from typing import List, Dict, Tuple
import asyncio
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer import PatternRecognizer


class PIIDetector:
    """
    Detects PII entities in text using Microsoft Presidio.
    
    This class only detects PII; it does not redact or modify text.
    """

    def add_custom_pattern(
        self,
        entity_name: str,
        regex_pattern: str,
        score: float = 0.5
    ) -> None:
        """
        Allow users to add custom PII patterns using regex.
        
        Args:
            entity_name: Name of custom entity (e.g., "EMPLOYEE_ID")
            regex_pattern: Regex pattern to match (e.g., r"\bEMP\d{6}\b")
            score: Confidence score (0-1)
            
        Example:
            >>> detector.add_custom_pattern(
            ...     "EMPLOYEE_ID",
            ...     r"\bEMP\d{6}\b",
            ...     score=0.8
            ... )
        """
        custom_recognizer = PatternRecognizer(
            supported_entity=entity_name,
            patterns=[{
                "name": f"{entity_name}_pattern",
                "regex": regex_pattern,
                "score": score
            }]
        )
        
        self.analyzer.add_recognizer(custom_recognizer)
        
        # Add to policy's entities if not already there
        if entity_name not in self.policy.entities:
            self.policy.entities.append(entity_name)
    def __init__(self, entities: List[str]):
        """
        Initialize PII detector.
        
        Args:
            entities: List of entity types to detect
        """
        self.entities = entities
        self.analyzer = AnalyzerEngine()
    
    async def detect(self, text: str) -> List[RecognizerResult]:
        """
        Detect PII entities in text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of detected PII entities with locations and scores
            
        Example:
            >>> detector = PIIDetector(["PERSON", "PHONE_NUMBER"])
            >>> results = await detector.detect("Call John at 555-0199")
            >>> [(r.entity_type, r.start, r.end) for r in results]
            [('PERSON', 5, 9), ('PHONE_NUMBER', 13, 21)]
        """
        loop = asyncio.get_event_loop()
        
        # Run Presidio analyzer in thread pool
        results = await loop.run_in_executor(
            None,
            lambda: self.analyzer.analyze(
                text=text,
                entities=self.entities,
                language="en"
            )
        )
        
        return results
    
    async def detect_batch(self, texts: List[str]) -> List[List[RecognizerResult]]:
        """
        Detect PII in multiple texts concurrently.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of detection results for each text
        """
        tasks = [self.detect(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    def extract_entity_types(self, results: List[RecognizerResult]) -> List[str]:
        """
        Extract unique entity types from detection results.
        
        Args:
            results: List of detection results
            
        Returns:
            List of unique entity types found (sorted)
        """
        entity_types = set(result.entity_type for result in results)
        return sorted(entity_types)
    
    def count_entities(self, results: List[RecognizerResult]) -> Dict[str, int]:
        """
        Count occurrences of each entity type.
        
        Args:
            results: List of detection results
            
        Returns:
            Dictionary mapping entity type to count
        """
        counts: Dict[str, int] = {}
        for result in results:
            counts[result.entity_type] = counts.get(result.entity_type, 0) + 1
        return counts