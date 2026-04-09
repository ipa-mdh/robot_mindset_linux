from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
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
BUNDLE_FORMAT_VERSION = 4


def _parse_python_version(version: str) -> tuple[int, int]:
    major, minor = version.split('.', 1)
    return int(major), int(minor)


def _python_abi_tag(version: str) -> str:
    major, minor = version.split('.', 1)
    return f'cp{major}{minor}'


def _python_version_digits(version: str) -> str:
    major, minor = version.split('.', 1)
    return f'{major}{minor}'


def _runtime_subdir_name(version: str) -> str:
    return _python_abi_tag(version)


def _extra_runtime_requirements(version: str) -> tuple[str, ...]:
    # pip download resolves some environment markers from the build interpreter,
    # so target-specific backports must be added explicitly for older runtimes.
    if _parse_python_version(version) < (3, 11):
        return ('exceptiongroup',)
    return ()


def _bundle_signature(version: str) -> str:
    payload = {
        'bundle_format_version': BUNDLE_FORMAT_VERSION,
        'requirements': REQUIREMENTS_PATH.read_text(encoding='utf-8'),
        'extra_requirements': list(_extra_runtime_requirements(version)),
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


def _copy_tree_contents(source_dir: Path, destination_dir: Path) -> None:
    for child in source_dir.iterdir():
        destination = destination_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, destination)


def _extract_wheel(wheel_path: Path, runtime_site_packages_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        extract_root = Path(tmpdir)
        with zipfile.ZipFile(wheel_path) as archive:
            archive.extractall(extract_root)

        for child in extract_root.iterdir():
            if child.name.endswith('.data') and child.is_dir():
                for scheme in ('purelib', 'platlib'):
                    scheme_dir = child / scheme
                    if scheme_dir.is_dir():
                        _copy_tree_contents(scheme_dir, runtime_site_packages_dir)
                continue
            destination = runtime_site_packages_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, destination)


def _extract_wheelhouse(wheelhouse_dir: Path, runtime_site_packages_dir: Path) -> None:
    for wheel_path in sorted(wheelhouse_dir.glob('*.whl')):
        _extract_wheel(wheel_path, runtime_site_packages_dir)


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
    extra_requirements = _extra_runtime_requirements(version)

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
            *extra_requirements,
        ],
        env=pip_env,
        check=True,
    )
    _extract_wheelhouse(wheelhouse_dir, runtime_site_packages_dir)
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
