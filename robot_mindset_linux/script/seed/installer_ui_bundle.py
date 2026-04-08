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
TARGET_PLATFORM = 'manylinux2014_x86_64'
TARGET_IMPLEMENTATION = 'cp'
SUPPORTED_TARGET_PYTHONS = ('3.8', '3.10', '3.12')
BUNDLE_FORMAT_VERSION = 2


def _python_abi_tag(version: str) -> str:
    major, minor = version.split('.', 1)
    return f'cp{major}{minor}'


def _python_version_digits(version: str) -> str:
    major, minor = version.split('.', 1)
    return f'{major}{minor}'


def _runtime_subdir_name(version: str) -> str:
    return _python_abi_tag(version)


def _bundle_signature(version: str) -> str:
    payload = {
        'bundle_format_version': BUNDLE_FORMAT_VERSION,
        'requirements': REQUIREMENTS_PATH.read_text(encoding='utf-8'),
        'target_python': version,
        'target_abi': _python_abi_tag(version),
        'platform': TARGET_PLATFORM,
        'implementation': TARGET_IMPLEMENTATION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def _resolve_cache_dir(version: str, cache_dir: Path | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir) / _runtime_subdir_name(version)
    return DEFAULT_CACHE_ROOT / _bundle_signature(version)


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


def _pip_target_args(version: str) -> list[str]:
    return [
        '--platform', TARGET_PLATFORM,
        '--implementation', TARGET_IMPLEMENTATION,
        '--python-version', _python_version_digits(version),
        '--abi', _python_abi_tag(version),
    ]


def _prepare_runtime_for_version(
    runtime_root: Path,
    version: str,
    cache_dir: Path | None,
    pip_env: dict[str, str],
) -> None:
    runtime_site_packages_dir = runtime_root / _runtime_subdir_name(version)
    resolved_cache_dir = _resolve_cache_dir(version, cache_dir)
    wheelhouse_dir = resolved_cache_dir / WHEELHOUSE_DIRNAME
    runtime_archive_path = resolved_cache_dir / RUNTIME_ARCHIVE_FILENAME
    target_args = _pip_target_args(version)

    if runtime_archive_path.exists():
        _extract_runtime(runtime_archive_path, runtime_site_packages_dir)
        return

    shutil.rmtree(runtime_site_packages_dir, ignore_errors=True)
    runtime_site_packages_dir.mkdir(parents=True, exist_ok=True)
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'download',
            '--isolated',
            *target_args,
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
            *target_args,
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


def prepare_installer_ui_bundle(
    autoinstall_dir: Path,
    context: dict | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Pre-install the offline Python runtimes for the installer NiceGUI UI."""
    autoinstall_dir = Path(autoinstall_dir)
    if not REQUIREMENTS_PATH.exists():
        raise FileNotFoundError(f'Installer UI requirements file not found: {REQUIREMENTS_PATH}')

    autoinstall_dir.mkdir(parents=True, exist_ok=True)
    runtime_requirements_path = autoinstall_dir / RUNTIME_REQUIREMENTS_FILENAME
    runtime_root = autoinstall_dir / RUNTIME_SITE_PACKAGES_DIRNAME
    runtime_requirements_path.write_text(REQUIREMENTS_PATH.read_text(encoding='utf-8'), encoding='utf-8')

    shutil.rmtree(runtime_root, ignore_errors=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    pip_env = _build_pip_env()

    for version in SUPPORTED_TARGET_PYTHONS:
        _prepare_runtime_for_version(runtime_root, version, cache_dir, pip_env)

    return runtime_root
