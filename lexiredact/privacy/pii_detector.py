"""
PII detection using Microsoft Presidio.

Detects personally identifiable information in text without modifying it.
"""
from typing import List, Dict, Any, Optional
import asyncio
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer import PatternRecognizer, Pattern


class PIIDetector:
    """
    Detects PII entities in text using Microsoft Presidio.

    This class only detects PII; it does not redact or modify text.
    """

    def __init__(
        self,
        entities: List[str],
        language: str = "en",
        score_threshold: Optional[float] = 0.0,
        allow_list: Optional[List[str]] = None,
        allow_list_match: str = "exact",
        custom_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize PII detector.

        Args:
            entities: List of entity types to detect
            language: Presidio analyzer language
            score_threshold: Minimum score to keep a recognition result
            allow_list: Values to skip during detection
            allow_list_match: Allow-list match mode ("exact" or "regex")
            custom_patterns: List of custom pattern definitions
        """
        self.entities = list(entities)
        self.language = language
        self.score_threshold = score_threshold
        self.allow_list = allow_list or []
        self.allow_list_match = allow_list_match
        self.analyzer = AnalyzerEngine()
        self._register_builtin_fallbacks()

        for pattern_config in custom_patterns or []:
            self.add_custom_pattern(
                entity_name=pattern_config["entity_name"],
                regex_pattern=pattern_config["regex_pattern"],
                score=pattern_config.get("score", 0.5),
                language=pattern_config.get("language"),
            )

    def add_custom_pattern(
        self,
        entity_name: str,
        regex_pattern: str,
        score: float = 0.5,
        language: Optional[str] = None,
    ) -> None:
        """
        Allow users to add custom PII patterns using regex.

        Args:
            entity_name: Name of custom entity (e.g., "EMPLOYEE_ID")
            regex_pattern: Regex pattern to match (e.g., r"\\bEMP\\d{6}\\b")
            score: Confidence score (0-1)
            language: Optional recognizer language override
        """
        custom_recognizer = PatternRecognizer(
            supported_entity=entity_name,
            supported_language=language or self.language,
            patterns=[
                Pattern(
                    name=f"{entity_name}_pattern",
                    regex=regex_pattern,
                    score=score,
                )
            ],
        )

        self.analyzer.registry.add_recognizer(custom_recognizer)

        if entity_name not in self.entities:
            self.entities.append(entity_name)

    def _register_builtin_fallbacks(self) -> None:
        """Register lightweight fallback recognizers for critical regex entities."""
        if "EMAIL_ADDRESS" in self.entities:
            email_recognizer = PatternRecognizer(
                supported_entity="EMAIL_ADDRESS",
                supported_language=self.language,
                patterns=[
                    Pattern(
                        name="EMAIL_ADDRESS_fallback",
                        regex=(
                            r"\b((([!#$%&'*+\-/=?^_`{|}~\w])|"
                            r"([!#$%&'*+\-/=?^_`{|}~\w]"
                            r"[!#$%&'*+\-/=?^_`{|}~\.\w]{0,}"
                            r"[!#$%&'*+\-/=?^_`{|}~\w]))"
                            r"[@]\w+([-.]\w+)*\.\w+([-.]\w+)*)\b"
                        ),
                        score=0.85,
                    )
                ],
                context=["email", "mail", "contact"],
            )
            self.analyzer.registry.add_recognizer(email_recognizer)

    async def detect(self, text: str) -> List[RecognizerResult]:
        """
        Detect PII entities in text.

        Args:
            text: Input text to analyze

        Returns:
            List of detected PII entities with locations and scores
        """
        loop = asyncio.get_event_loop()

        results = await loop.run_in_executor(
            None,
            lambda: self.analyzer.analyze(
                text=text,
                entities=self.entities,
                language=self.language,
                score_threshold=self.score_threshold,
                allow_list=self.allow_list,
                allow_list_match=self.allow_list_match,
            ),
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
