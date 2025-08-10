
# python3 script/generate_autoinstall.py

# bash script/build-seed-iso.sh
from copy import deepcopy
from pathlib import Path
import shutil
from loguru import logger

from utils.utils import get_config
from seed.render_all import Render
from seed.geniso import create_seed_iso

def find_and_merge_environment(base_context, context):
    """
    This function finds the environment in the main YAML that matches the one in the input YAML
    and merges the input data into it. It returns the merged environment.
    Args:
        base_context (dict): Main YAML data containing environments.
        context (dict): Input YAML data containing the environment to merge.
    Returns:
        dict: Merged environment data.
        
    Example:
        base_context = {
            "environments": [
                {"environment": "env1", "data": {}},
                {"environment": "env2", "data": {}}
            ]
        }
        context = {
            "environment": "env1",
            "data": {"key": "value"}
        }
        find_and_merge_environment(base_context, context)
        # Returns: {"environment": "env1", "data": {"key": "value"}}
    Raises:
        ValueError: If the environment is not found in the main YAML or if the input YAML does not specify an environment.
    """
    target_env_name = context.get("environment")
    if not target_env_name:
        raise ValueError("Input YAML does not specify an 'environment'.")

    # Remove 'environment' key, keep the rest for merging
    context_to_merge = {k: v for k, v in context.items() if k != "environment"}

    environments = base_context.get("environments", [])
    for env in environments:
        if env.get("environment") == target_env_name:
            env_copy = deepcopy(env)  # Avoid modifying the original
            # Merge input data into the environment copy
            for key, value in context_to_merge.items():
                if isinstance(value, dict) and isinstance(env_copy.get(key), dict):
                    env_copy[key].update(value)  # Shallow merge if both are dicts
                else:
                    env_copy[key] = value  # Overwrite or add new keys
            return env_copy

    raise ValueError(f"Environment '{target_env_name}' not found in main YAML.")

def copy_paths(data, destination):
    """
    This function will copy the files and directories specified in the data dictionary
    to the destination directory, preserving their names. If the destination directory does not exist,
    it will be created. If a source path does not exist, an error will be logged.
    
    Args:
        data (dict): Dictionary with names and paths to copy.
        destination (Path): Destination directory.
    Example:
        data = {
            "file1": "/path/to/file1",
            "dir1": "/path/to/dir1"
            "dir2": {"dir1": "/path/to/dir2/dir1",
                     "file2": "/path/to/dir2/file2"}
        }
        copy_paths(data, Path("/destination"))
        
        Output folder structure:
            └── destination
                ├── file1
                └── dir1
                    ├── dir1
                    └── file2
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)  # Ensure destination exists

    for name, source_path in data.items():
        print(f"{name}, {source_path}")
        source = Path(source_path)
        dest = destination / source.name  # Keep the original name under destination

        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, dest)
        else:
            logger.error(f"Source '{source}' does not exist.")

def get_context(base_context_path=Path("config/base_context.yaml"),
         context_path=Path("config/context.yaml")):
    """
    Load and merge the base context with the specific context.
    Args:
        base_context_path (Path): Path to the base context YAML file.
        context_path (Path): Path to the specific context YAML file.
    Returns:
        dict: Merged context.
    """
    base_context = get_config(base_context_path)
    context_config = get_config(context_path)

    context = find_and_merge_environment(base_context, context_config)

    return context

def main(base_context: dict,
         context: dict,
         output_dir=Path("output")):
    """
    Main function to generate the seed ISO.
    Args:
        base_context (dict): Base configuration of the context.
        context (dict): Context for the seed generation.
        output_dir (Path): Directory to save the generated ISO.
    """
    # Check if the output directory exists, if not create it
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    context = find_and_merge_environment(base_context, context)

    logger.debug(context)

    r = Render(destination=output_dir,
               context=context)

    copy_paths(context["data"], output_dir/"seed/data")

    rv = create_seed_iso(seed_dir=output_dir/"seed",
                    output_dir=output_dir)
    
    return rv

if __name__ == "__main__":
    """ Main entry point for the script. """
    # Define paths
    output_dir=Path("output")
    context_path=Path("config/seed/context.yaml")
    base_context_path=Path("config/seed/base_context.yaml")
    
    # get config
    base_context = get_config(base_context_path)
    context = get_config(context_path)
    
    main(base_context, context, output_dir)