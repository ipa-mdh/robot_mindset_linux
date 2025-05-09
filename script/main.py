from pathlib import Path
from loguru import logger

from seed.seed import main as seed_main
from utils.utils import get_config

from nicegui import ui
from gui.main import SeedStepperUI

def main():
    # Define paths
    output_dir=Path("output")
    
    # config paths
    # base_context_path=Path("config/seed/base_context.yaml")
    context_path=Path("config/seed/context.yaml")
    
    # Get config
    # base_context = get_config(base_context_path)
    context = get_config(context_path)
    
    # Call the main function from the seed module
    seed_main(base_context=context,
              context=context,
              output_dir=output_dir)

def create_seed_iso(context):
    seed_main(
        base_context=context,
        context=context,
        output_dir=Path("output")
    )
    
# if __name__ == "__main__":
#     main()

if __name__ in {"__main__", "__mp_main__"}:
    # Load the YAML configuration
    context_path=Path("config/seed/context.yaml")
    context = get_config(context_path)

    # Create the GUI
    css = SeedStepperUI(context, callback_create_seed=lambda e: (
        ui.notify('Creating Seed ISO...'),
        logger.debug(f"Creating seed ISO with context: {e}"),
        create_seed_iso(e),
        ui.notify('Seed ISO created successfully!')
    ))
    
    ui.run(title='Robot Mindset Linux', port=8080)