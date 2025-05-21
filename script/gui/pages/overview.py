from pathlib import Path
from loguru import logger
import yaml
import anyio


from nicegui import ui, app, run

from .. import theme
from ..loguru_sink import LoguruSink
from ..message import message

from ..utils.user_storage import UserStorage
from ..seed_stepper_ui import SeedStepperUI

from seed.seed import main as seed_main
from utils.utils import get_config

from nicegui import ui
# from gui.main import SeedStepperUI

from ..utils.long_running_task import controlled_task

semaphore = anyio.Semaphore(5)

@controlled_task(semaphore)
async def create_seed_iso(context, output_dir: Path):
    """Create a seed ISO using the provided context."""
    
    rv = await run.cpu_bound(seed_main,
            context,
            context,
            output_dir
        )
    return rv

def save_context_callback(context, file_path:Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as outfile:
        yaml.dump(context, outfile)


# Build the UI
def content(data: UserStorage) -> None:
    # Load the YAML configuration
    context = get_config(data.context_path)

    # Create the GUI
    css = SeedStepperUI(context,
                        callback_save_context=save_context_callback,
                        callback_create_seed=create_seed_iso,
                        data=data)