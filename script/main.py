
# python3 script/generate_autoinstall.py

# bash script/build-seed-iso.sh
from copy import deepcopy
from pathlib import Path
import shutil
import yaml
from loguru import logger

from render_all import Render
from geniso import create_seed_iso

def get_config(path:Path):
    processed = {}
    if path.exists():
        with open(path, "r") as f:
            processed = yaml.safe_load(f)
    else:
        logger.error(f"File not found: {path}")
        raise FileNotFoundError(f"File not found: {path}")
    return processed

def find_environment(main_data, input_data):
    target_env_name = input_data.get("environment")
    if target_env_name is None:
        raise ValueError("Input YAML does not specify an 'environment'.")

    environments = main_data.get("environment", [])
    for env in environments:
        if env.get("name") == target_env_name:
            return env

    raise ValueError(f"Environment '{target_env_name}' not found in main YAML.")

def find_and_merge_environment(main_data, input_data):

    target_env_name = input_data.get("environment")
    if not target_env_name:
        raise ValueError("Input YAML does not specify an 'environment'.")

    # Remove 'environment' key, keep the rest for merging
    input_data_to_merge = {k: v for k, v in input_data.items() if k != "environment"}

    environments = main_data.get("environments", [])
    for env in environments:
        if env.get("environment") == target_env_name:
            env_copy = deepcopy(env)  # Avoid modifying the original
            # Merge input data into the environment copy
            for key, value in input_data_to_merge.items():
                if isinstance(value, dict) and isinstance(env_copy.get(key), dict):
                    env_copy[key].update(value)  # Shallow merge if both are dicts
                else:
                    env_copy[key] = value  # Overwrite or add new keys
            return env_copy

    raise ValueError(f"Environment '{target_env_name}' not found in main YAML.")

def copy_paths(data, destination):
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
            raise FileNotFoundError(f"Source '{source}' does not exist.")

def get_context(intern_config_path=Path("config/intern.yaml"),
         context_path=Path("config/context.yaml")):
    
    intern_config = get_config(intern_config_path)
    context_config = get_config(context_path)

    context = find_and_merge_environment(intern_config, context_config)

    return context

def main():
    output_dir = Path("output")

    intern_config_path = Path("config/intern.yaml")
    context_path = Path("config/context.yaml")

    context = get_context(intern_config_path, context_path)

    logger.debug(context)

    r = Render(destination=output_dir,
               context=context)

    copy_paths(context["data"], output_dir/"seed/data")

    create_seed_iso(seed_dir=output_dir/"seed",
                    output_dir=output_dir)

if __name__ == "__main__":
    main()