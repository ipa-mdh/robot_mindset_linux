from pathlib import Path
import subprocess
from loguru import logger

def create_seed_iso(seed_dir, output_dir=Path("output")):
    rv = False
    seed_folder = Path(seed_dir)
    output_dir = Path(output_dir)
    seed_iso = output_dir / "seed.iso"

    # Make sure the seed folder exists
    if not seed_folder.is_dir():
        raise FileNotFoundError(f"Seed folder '{seed_folder}' does not exist.")

    # Build the genisoimage command
    command = [
        "genisoimage",
        "-output", str(seed_iso),
        "-volid", "CIDATA",
        "-joliet",
        "-rock",
        str(seed_folder)
    ]

    # Run the command
    try:
        subprocess.run(command, check=True)
        logger.info(f"Successfully created ISO: {seed_iso}")
        rv = True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating ISO: {e}")
        rv = False
        
    return rv