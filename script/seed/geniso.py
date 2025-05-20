from pathlib import Path
import subprocess

def create_seed_iso(seed_dir, output_dir=Path("output")):
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
        print(f"Successfully created ISO: {seed_iso}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating ISO: {e}")