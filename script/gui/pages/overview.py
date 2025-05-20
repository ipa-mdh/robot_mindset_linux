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
    seed_main(
        base_context=context,
        context=context,
        output_dir=output_dir
    )

def dump_context(data, file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as outfile:
        yaml.dump(data, outfile)


# Build the UI
def content(data: UserStorage) -> None:
    # Load the YAML configuration
    context_path = data.work_dir / "context.yaml"
    context = get_config(context_path)

    # Create the GUI
    css = SeedStepperUI(context,
                        call_back_save_context=lambda e: (
                            ui.notify('Saving Context...'),
                            logger.debug(f"Saving context: {e}"),
                            dump_context(e, context_path),
                            ui.notify('Context saved successfully!')
                        ),
                        callback_create_seed=lambda e: (
                            ui.notify('Creating Seed ISO...'),
                            logger.debug(f"Creating seed ISO with context: {e}"),
                            dump_context(e, context_path),
                            create_seed_iso(e, data.work_dir),
                            ui.notify('Seed ISO created successfully!')
                        ),
                        data=data)