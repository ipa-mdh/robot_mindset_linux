from enum import Enum
from jinja2 import Template
from pathlib import Path
import shutil
import yaml
from loguru import logger
from utils.environment_targets import normalize_environment_name


def render_path(path: Path, context: dict) -> Path:
    """Render each part of the path as a Jinja2 template."""
    parts = []
    for part in path.parts:
        rendered = Template(part).render(args=context)
        parts.append(rendered)

    logger.debug(f"Rendering path: {path} -> {parts}")
    return Path(*parts)


def render_template_folder(template_root: Path, destination_root: Path, context: dict):
    """Render the template folder and copy files to the destination."""
    for file in template_root.rglob('*'):
        logger.info(f"Processing file: {file}")

        rel_path = file.relative_to(template_root)
        dest_path = destination_root / render_path(rel_path, context)
        logger.debug(f"Destination path: {dest_path}")

        if dest_path.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)

        elif file.suffix == '.j2':
            with open(file) as f:
                template = Template(f.read())
                rendered = template.render(args=context)
            dest_path = dest_path.with_suffix('')
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, 'w') as f:
                f.write(rendered)
        else:
            if file.is_file():
                logger.debug(f"Copying file: {file} to {dest_path}")
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src=file, dst=dest_path)


def get_template_folder(environment: str):
    """
    Get the template folder based on the Ubuntu version target.
    Arguments:
    - environment: The Ubuntu version target for which the template is needed (e.g., "22.04").
    Returns:
    - template_root: The path to the template folder.
    """
    current_file_path = Path(__file__).resolve()
    parent_dir = current_file_path.parent

    def dot_to_underscore(string: str):
        if not isinstance(string, str):
            string = str(string)
        return string.replace('.', '_')

    normalized_environment = normalize_environment_name(environment)
    template_root = parent_dir / Path('template') / dot_to_underscore(normalized_environment)
    if not template_root.exists():
        logger.error(f"Template directory {template_root} does not exist.")
        raise ValueError(f"Unknown environment: {normalized_environment}")

    return template_root


class Render():
    def __init__(self, destination: Path, context: dict):
        self.context = context

        self.working_dir = destination
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.init()

    def init(self):
        """
        Initialize the package by creating the necessary directories and files.
        """
        env = self.context['environment']
        template_root = get_template_folder(env)
        render_template_folder(template_root, self.working_dir, self.context)
