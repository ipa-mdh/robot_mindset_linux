from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parent / 'installer_ui_requirements.txt'
RUNTIME_REQUIREMENTS_FILENAME = 'requirements-installer-ui.txt'
RUNTIME_SITE_PACKAGES_DIRNAME = 'installer-ui-site-packages'


def prepare_installer_ui_bundle(autoinstall_dir: Path) -> Path:
    """Pre-install the offline Python runtime for the installer NiceGUI UI."""
    autoinstall_dir = Path(autoinstall_dir)
    if not REQUIREMENTS_PATH.exists():
        raise FileNotFoundError(f'Installer UI requirements file not found: {REQUIREMENTS_PATH}')

    autoinstall_dir.mkdir(parents=True, exist_ok=True)
    runtime_requirements_path = autoinstall_dir / RUNTIME_REQUIREMENTS_FILENAME
    runtime_site_packages_dir = autoinstall_dir / RUNTIME_SITE_PACKAGES_DIRNAME

    runtime_requirements_path.write_text(REQUIREMENTS_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    shutil.rmtree(runtime_site_packages_dir, ignore_errors=True)
    runtime_site_packages_dir.mkdir(parents=True, exist_ok=True)

    pip_env = os.environ.copy()
    pip_env['PYTHONNOUSERSITE'] = '1'
    pip_env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    pip_env['PIP_NO_INPUT'] = '1'

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--isolated',
            '--ignore-installed',
            '--target',
            str(runtime_site_packages_dir),
            '--requirement',
            str(REQUIREMENTS_PATH),
            '--only-binary=:all:',
            '--no-compile',
            '--upgrade',
            '--no-warn-script-location',
        ],
        env=pip_env,
        check=True,
    )
    return runtime_site_packages_dir
