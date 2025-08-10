from pathlib import Path
import yaml
from loguru import logger

def get_config(path:Path, default=Path("config/seed/context.yaml")) -> dict:
    """
    Load a YAML configuration file.
    Args:
        path (Path): Path to the YAML file.
    Returns:
        dict: Parsed YAML content.
    """
    use_default = False
    
    if not isinstance(path, Path):
        logger.error(f"Invalid path type: {type(path)}. Expected Path.")
        raise TypeError(f"Invalid path type: {type(path)}. Expected Path.")
    if not path.suffix == ".yaml":
        logger.error(f"Invalid file type: {path.suffix}. Expected .yaml")
        raise ValueError(f"Invalid file type: {path.suffix}. Expected .yaml")
    if not path.exists():
        logger.warning(f"File not found: {path}")
        use_default = True
        # raise FileNotFoundError(f"File not found: {default}")
    if not path.is_file():
        logger.warning(f"Path is not a file: {path}")
        use_default = True
        # raise IsADirectoryError(f"Path is not a file: {path}")
    
    if use_default:
        if not default.exists():
            logger.error(f"Default file not found: {default}")
            raise FileNotFoundError(f"Default file not found: {default}")
        p = default
    else:
        p = path
        
    config = {}
    with open(p, "r") as f:
        config = yaml.safe_load(f)
    
    return config