from pathlib import Path
from loguru import logger
import yaml
import json
import uuid

from seed.seed import main as seed_main

from nicegui import ui
# from gui.main import SeedStepperUI

from gui.create_pages import create

def create_seed_iso(context):
    seed_main(
        base_context=context,
        context=context,
        output_dir=Path("output")
    )

def dump_context(data, file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as outfile:
        yaml.dump(data, outfile)


# if __name__ == "__main__":
#     main()

if __name__ in {"__main__", "__mp_main__"}:
    # Load the YAML configuration
    # context_path=Path("config/seed/context.yaml")
    # output_context_path=Path("config/seed/context_out.yaml")
    # context = get_config(context_path)
    
    create()
    
    ui.run(title='Robot Mindset Linux', port=8080, storage_secret='seakjshzd7u23cret', favicon='script/gui/image/robot_mindset_icon.ico')