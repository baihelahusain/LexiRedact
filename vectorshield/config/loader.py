"""
Configuration loader for VectorShield.

Supports loading from dictionaries or YAML files.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from .defaults import validate_config, get_default_config


def load_config(
    config_dict: Optional[Dict[str, Any]] = None,
    config_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load and validate configuration.
    
    Priority order:
    1. Values from config_dict (if provided)
    2. Values from config_file (if provided)
    3. Default values
    
    Args:
        config_dict: Configuration dictionary (optional)
        config_file: Path to YAML config file (optional)
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid
        FileNotFoundError: If config_file doesn't exist
        
    Examples:
        >>> # Use defaults
        >>> config = load_config()
        
        >>> # Override specific values
        >>> config = load_config(config_dict={
        ...     "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        ...     "cache_backend": "redis"
        ... })
        
        >>> # Load from file
        >>> config = load_config(config_file="config.yaml")
    """
    # Start with defaults
    config = get_default_config()
    
    # Load from file if provided
    if config_file is not None:
        file_config = _load_from_yaml(config_file)
        config.update(file_config)
    
    # Override with dict if provided
    if config_dict is not None:
        config.update(config_dict)
    
    # Validate and return
    return validate_config(config)


def _load_from_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ImportError: If PyYAML is not installed
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required to load config from YAML files. "
            "Install with: pip install pyyaml"
        )
    
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config if config is not None else {}


def save_config_to_yaml(config: Dict[str, Any], file_path: str) -> None:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration dictionary
        file_path: Path to save YAML file
        
    Raises:
        ImportError: If PyYAML is not installed
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required to save config to YAML files. "
            "Install with: pip install pyyaml"
        )
    
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)