from pathlib import Path
import yaml
from loguru import logger

def get_config(path:Path):
    """
    Load a YAML configuration file.
    Args:
        path (Path): Path to the YAML file.
    Returns:
        dict: Parsed YAML content.
    """
    if not isinstance(path, Path):
        logger.error(f"Invalid path type: {type(path)}. Expected Path.")
        raise TypeError(f"Invalid path type: {type(path)}. Expected Path.")
    if not path.suffix == ".yaml":
        logger.error(f"Invalid file type: {path.suffix}. Expected .yaml")
        raise ValueError(f"Invalid file type: {path.suffix}. Expected .yaml")
    if not path.exists():
        logger.error(f"File not found: {path}")
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        logger.error(f"Path is not a file: {path}")
        raise IsADirectoryError(f"Path is not a file: {path}")
    
    config = {}
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    
    return config