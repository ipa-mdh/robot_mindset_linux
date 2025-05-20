from pathlib import Path
from loguru import logger
import yaml

from nicegui import ui, app

from .. import theme
from ..loguru_sink import LoguruSink
from ..message import message

from ..utils.user_storage import UserStorage
from ..seed_stepper_ui import SeedStepperUI

from seed.seed import main as seed_main
from utils.utils import get_config

from nicegui import ui
# from gui.main import SeedStepperUI

def create_seed_iso(context, output_dir: Path):
    """Create a seed ISO using the provided context."""
    return seed_main(
            base_context=context,
            context=context,
            output_dir=output_dir
        )

def dump_context(data, file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as outfile:
        yaml.dump(data, outfile)


def save_context_callback(context, context_path):
    logger.debug(f"Saving context: {context}")
    dump_context(context, context_path)


# Build the UI
def content(data: UserStorage) -> None:
    # Load the YAML configuration
    context = get_config(data.context_path)

    # Create the GUI
    css = SeedStepperUI(context,
                        callback_save_context=save_context_callback,
                        callback_create_seed=create_seed_iso,
                        data=data)