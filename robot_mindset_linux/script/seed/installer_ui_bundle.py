from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parent / 'installer_ui_requirements.txt'
RUNTIME_REQUIREMENTS_FILENAME = 'requirements-installer-ui.txt'
RUNTIME_SITE_PACKAGES_DIRNAME = 'installer-ui-site-packages'
DEFAULT_CACHE_ROOT = Path(
    os.environ.get('ROBOT_MINDSET_INSTALLER_UI_CACHE_DIR', '/tmp/robot_mindset_linux_installer_ui_cache')
)
WHEELHOUSE_DIRNAME = 'wheelhouse'
RUNTIME_ARCHIVE_FILENAME = 'installer-ui-site-packages.tar'


def _bundle_signature() -> str:
    payload = {
        'requirements': REQUIREMENTS_PATH.read_text(encoding='utf-8'),
        'python': f'{sys.version_info.major}.{sys.version_info.minor}',
        'platform': sys.platform,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def _resolve_cache_dir(cache_dir: Path | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir)
    return DEFAULT_CACHE_ROOT / _bundle_signature()


def _build_pip_env() -> dict[str, str]:
    pip_env = os.environ.copy()
    pip_env['PYTHONNOUSERSITE'] = '1'
    pip_env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    pip_env['PIP_NO_INPUT'] = '1'
    return pip_env


def _archive_runtime(runtime_site_packages_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, 'w') as tar:
        for child in sorted(runtime_site_packages_dir.rglob('*')):
            tar.add(child, arcname=str(child.relative_to(runtime_site_packages_dir)))


def _extract_runtime(archive_path: Path, runtime_site_packages_dir: Path) -> None:
    shutil.rmtree(runtime_site_packages_dir, ignore_errors=True)
    runtime_site_packages_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path) as tar:
        tar.extractall(runtime_site_packages_dir)


def prepare_installer_ui_bundle(autoinstall_dir: Path, cache_dir: Path | None = None) -> Path:
    """Pre-install the offline Python runtime for the installer NiceGUI UI."""
    autoinstall_dir = Path(autoinstall_dir)
    if not REQUIREMENTS_PATH.exists():
        raise FileNotFoundError(f'Installer UI requirements file not found: {REQUIREMENTS_PATH}')

    autoinstall_dir.mkdir(parents=True, exist_ok=True)
    runtime_requirements_path = autoinstall_dir / RUNTIME_REQUIREMENTS_FILENAME
    runtime_site_packages_dir = autoinstall_dir / RUNTIME_SITE_PACKAGES_DIRNAME
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
    wheelhouse_dir = resolved_cache_dir / WHEELHOUSE_DIRNAME
    runtime_archive_path = resolved_cache_dir / RUNTIME_ARCHIVE_FILENAME

    runtime_requirements_path.write_text(REQUIREMENTS_PATH.read_text(encoding='utf-8'), encoding='utf-8')

    if runtime_archive_path.exists():
        _extract_runtime(runtime_archive_path, runtime_site_packages_dir)
        return runtime_site_packages_dir

    shutil.rmtree(runtime_site_packages_dir, ignore_errors=True)
    runtime_site_packages_dir.mkdir(parents=True, exist_ok=True)
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)

    pip_env = _build_pip_env()

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'download',
            '--isolated',
            '--dest',
            str(wheelhouse_dir),
            '--requirement',
            str(REQUIREMENTS_PATH),
            '--only-binary=:all:',
        ],
        env=pip_env,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--isolated',
            '--ignore-installed',
            '--no-index',
            f'--find-links={wheelhouse_dir}',
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
    _archive_runtime(runtime_site_packages_dir, runtime_archive_path)
    return runtime_site_packages_dir
