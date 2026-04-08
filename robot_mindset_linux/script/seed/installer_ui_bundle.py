from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parent / 'installer_ui_requirements.txt'
RUNTIME_REQUIREMENTS_FILENAME = 'requirements-installer-ui.txt'
WHEELHOUSE_DIRNAME = 'wheelhouse'


def prepare_installer_ui_bundle(autoinstall_dir: Path) -> Path:
    """Download offline Python wheels for the installer NiceGUI runtime."""
    autoinstall_dir = Path(autoinstall_dir)
    if not REQUIREMENTS_PATH.exists():
        raise FileNotFoundError(f'Installer UI requirements file not found: {REQUIREMENTS_PATH}')

    autoinstall_dir.mkdir(parents=True, exist_ok=True)
    runtime_requirements_path = autoinstall_dir / RUNTIME_REQUIREMENTS_FILENAME
    wheelhouse_dir = autoinstall_dir / WHEELHOUSE_DIRNAME

    runtime_requirements_path.write_text(REQUIREMENTS_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    shutil.rmtree(wheelhouse_dir, ignore_errors=True)
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'download',
            '--dest',
            str(wheelhouse_dir),
            '--only-binary=:all:',
            '-r',
            str(REQUIREMENTS_PATH),
        ],
        check=True,
    )
    return wheelhouse_dir
