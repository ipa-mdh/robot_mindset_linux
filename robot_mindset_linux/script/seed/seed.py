
# python3 script/generate_autoinstall.py

# bash script/build-seed-iso.sh
from copy import deepcopy
from pathlib import Path
import shutil
import tarfile
from loguru import logger

from utils.environment_targets import normalize_context_environment_model
from utils.utils import get_config
from seed.render_all import Render
from seed.geniso import create_seed_iso
from seed.offline_bundle import prepare_offline_bundle
from seed.installer_ui_bundle import prepare_installer_ui_bundle


def find_and_merge_environment(base_context, context):
    """
    This function finds the environment in the main YAML that matches the one in the input YAML
    and merges the input data into it. It returns the merged environment.
    Args:
        base_context (dict): Main YAML data containing environments.
        context (dict): Input YAML data containing the environment to merge.
    Returns:
        dict: Merged environment data.
    Raises:
        ValueError: If the environment is not found in the main YAML or if the input YAML does not specify an environment.
    """
    base_context = normalize_context_environment_model(deepcopy(base_context))
    context = normalize_context_environment_model(deepcopy(context))

    target_env_name = context.get('environment')
    if not target_env_name:
        raise ValueError("Input YAML does not specify an 'environment'.")

    context_to_merge = {k: v for k, v in context.items() if k != 'environment'}

    environments = base_context.get('environments', [])
    for env in environments:
        if env.get('environment') == target_env_name:
            env_copy = deepcopy(env)
            for key, value in context_to_merge.items():
                if isinstance(value, dict) and isinstance(env_copy.get(key), dict):
                    env_copy[key].update(value)
                else:
                    env_copy[key] = value
            return env_copy

    raise ValueError(f"Environment '{target_env_name}' not found in main YAML.")


def copy_paths(data, destination):
    """Copy the files and directories specified in the data dictionary to the destination directory."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    for name, source_path in data.items():
        print(f"{name}, {source_path}")
        source = Path(source_path)
        dest = destination / source.name

        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, dest)
        else:
            logger.error(f"Source '{source}' does not exist.")


def archive_seed_payloads(seed_data_dir: Path) -> tuple[Path, Path]:
    """Archive the rendered seed data folder into separate early and target payloads."""
    seed_data_dir = Path(seed_data_dir)
    seed_dir = seed_data_dir.parent
    early_archive_path = seed_dir / 'early-data.tar'
    target_archive_path = seed_dir / 'target-data.tar'
    legacy_archive_path = seed_dir / 'data.tar'
    autoinstall_dir = seed_data_dir / 'autoinstall'

    if not autoinstall_dir.is_dir():
        raise FileNotFoundError(f"autoinstall payload not found in {seed_data_dir}")

    legacy_archive_path.unlink(missing_ok=True)
    early_archive_path.unlink(missing_ok=True)
    with tarfile.open(early_archive_path, 'w') as tar:
        tar.add(autoinstall_dir, arcname='data/autoinstall', recursive=True)

    target_archive_path.unlink(missing_ok=True)
    with tarfile.open(target_archive_path, 'w') as tar:
        tar.add(seed_data_dir, arcname='data', recursive=True)

    shutil.rmtree(seed_data_dir)
    return early_archive_path, target_archive_path


def get_context(base_context_path=Path('config/seed/context.yaml'),
         context_path=Path('config/seed/context.yaml')):
    """Load and merge the base context with the specific context."""
    base_context = normalize_context_environment_model(get_config(base_context_path))
    context_config = normalize_context_environment_model(get_config(context_path))

    context = find_and_merge_environment(base_context, context_config)

    return context


def main(base_context: dict,
         context: dict,
         output_dir=Path('output')):
    """Main function to generate the seed ISO."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    base_context = normalize_context_environment_model(deepcopy(base_context))
    context = normalize_context_environment_model(deepcopy(context))
    context = find_and_merge_environment(base_context, context)

    logger.debug(context)

    Render(destination=output_dir, context=context)

    copy_paths(context.get('data', {}), output_dir / 'seed/data')
    prepare_offline_bundle(seed_data_dir=output_dir / 'seed/data', context=context)
    prepare_installer_ui_bundle(output_dir / 'seed/data/autoinstall')
    archive_seed_payloads(output_dir / 'seed/data')

    rv = create_seed_iso(seed_dir=output_dir / 'seed', output_dir=output_dir)

    return rv


if __name__ == '__main__':
    """ Main entry point for the script. """
    output_dir = Path('output')
    context_path = Path('config/seed/context.yaml')
    base_context_path = Path('config/seed/context.yaml')

    base_context = get_config(base_context_path)
    context = get_config(context_path)

    main(base_context, context, output_dir)
