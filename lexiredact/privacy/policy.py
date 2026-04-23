"""
PII entity policy management for LexiRedact.

Defines which types of PII should be detected and how to handle them.
"""
from typing import List, Set, Dict


class PIIPolicy:
    """
    Manages PII detection policy.
    
    Defines which entity types should be detected and provides
    metadata about entity handling.
    """
    
    # All supported PII entity types
    ALL_ENTITIES = [
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "US_SSN",
        "LOCATION",
        "DATE_TIME",
        "MEDICAL_LICENSE",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "US_ITIN",
        "US_BANK_NUMBER",
        "IBAN_CODE",
        "IP_ADDRESS",
        "URL",
        "CRYPTO",
        "NRP",  # Nationality/Religious/Political group
        "AGE",
    ]
    
    # High-sensitivity entities (PHI/financial)
    HIGH_SENSITIVITY = [
        "US_SSN",
        "CREDIT_CARD",
        "US_BANK_NUMBER",
        "MEDICAL_LICENSE",
        "US_PASSPORT",
    ]
    
    # Medium-sensitivity entities
    MEDIUM_SENSITIVITY = [
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "LOCATION",
    ]
    
    def __init__(self, entities: List[str] = None):
        """
        Initialize PII policy.
        
        Args:
            entities: List of entity types to detect.
                     If None, uses all supported entities.
        """
        if entities is None:
            self.entities = self.ALL_ENTITIES.copy()
        else:
            # Allow custom Presidio recognizer entities in addition to built-ins.
            self.entities = entities
        
        self._entity_set = set(self.entities)
    
    def should_detect(self, entity_type: str) -> bool:
        """Check if an entity type should be detected."""
        return entity_type in self._entity_set
    
    def get_sensitivity(self, entity_type: str) -> str:
        """
        Get sensitivity level of an entity type.
        
        Returns:
            "high", "medium", or "low"
        """
        if entity_type in self.HIGH_SENSITIVITY:
            return "high"
        elif entity_type in self.MEDIUM_SENSITIVITY:
            return "medium"
        else:
            return "low"
    
    def add_entity(self, entity_type: str) -> None:
        """Add an entity type to the detection policy."""
        if entity_type not in self._entity_set:
            self.entities.append(entity_type)
            self._entity_set.add(entity_type)
    
    def remove_entity(self, entity_type: str) -> None:
        """Remove an entity type from the detection policy."""
        if entity_type in self._entity_set:
            self.entities.remove(entity_type)
            self._entity_set.remove(entity_type)
    
    def get_entity_list(self) -> List[str]:
        """Get list of entity types being detected."""
        return self.entities.copy()
    
    @classmethod
    def create_minimal(cls) -> "PIIPolicy":
        """
        Create policy with only high-sensitivity entities.
        
        Returns:
            PIIPolicy configured for high-sensitivity entities only
        """
        return cls(entities=cls.HIGH_SENSITIVITY.copy())
    
    @classmethod
    def create_standard(cls) -> "PIIPolicy":
        """
        Create policy with high and medium sensitivity entities.
        
        Returns:
            PIIPolicy configured for standard use cases
        """
        entities = cls.HIGH_SENSITIVITY + cls.MEDIUM_SENSITIVITY
        return cls(entities=entities)
    
    @classmethod
    def create_comprehensive(cls) -> "PIIPolicy":
        """
        Create policy with all supported entities.
        
        Returns:
            PIIPolicy configured to detect all PII types
        """
        return cls(entities=cls.ALL_ENTITIES.copy())
