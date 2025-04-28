from pathlib import Path
from seed.seed import main as seed_main
from utils.utils import get_config


def main():
    # Define paths
    output_dir=Path("output")
    
    # config paths
    context_path=Path("config/seed/context.yaml")
    base_context_path=Path("config/seed/base_context.yaml")
    
    # Get config
    base_context = get_config(base_context_path)
    context = get_config(context_path)
    # Call the main function from the seed module
    seed_main(base_context=base_context,
              context=context,
              output_dir=output_dir)
    
    
if __name__ == "__main__":
    main()