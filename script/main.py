# #!/bin/bash

# python3 script/generate_autoinstall.py

# bash script/build-seed-iso.sh
from pathlib import Path

from render_all import Render

def main():
    context_path = Path("config/context.yaml")
    dest = Path("output") / "seed"
    r = Render(destination=dest, config_path=context_path)


if __name__ == "__main__":
    main()