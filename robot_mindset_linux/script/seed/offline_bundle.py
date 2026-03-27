from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError

import yaml
from loguru import logger


MANIFEST_PATH = Path(__file__).resolve().parent / 'offline' / 'manifest.yaml'
DEFAULT_CACHE_ROOT = Path(os.environ.get('ROBOT_MINDSET_OFFLINE_CACHE_DIR', '/tmp/robot_mindset_linux_offline_cache'))
APT_LIST_MAX_AGE_SECONDS = 24 * 60 * 60
UBUNTU_RELEASES = {
    '20.04': 'focal',
    '22.04': 'jammy',
    '24.04': 'noble',
}


def _expected_ubuntu_version(context: dict) -> str | None:
    image_name = str(context.get('image', ''))
    if not image_name.startswith('ubuntu-'):
        return None
    parts = image_name.split('-')
    if len(parts) < 2:
        return None
    version_parts = parts[1].split('.')
    if len(version_parts) < 2:
        return None
    return '.'.join(version_parts[:2])


def _target_ubuntu_release(context: dict) -> str:
    configured_release = context.get('ubuntu_release')
    if configured_release:
        return str(configured_release)

    expected_version = _expected_ubuntu_version(context)
    if expected_version in UBUNTU_RELEASES:
        return UBUNTU_RELEASES[expected_version]

    raise RuntimeError(
        'could not determine the Ubuntu release for the offline dependency bundle; '
        f'selected target image is {context.get("image", "unknown")}'
    )


def _load_manifest() -> dict:
    with MANIFEST_PATH.open() as handle:
        return yaml.safe_load(handle) or {}


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        logger.info('Reusing cached download {}', destination)
        return
    logger.info('Downloading {} -> {}', url, destination)
    try:
        urllib.request.urlretrieve(url, destination)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f'failed to download {url} -> {destination}: {exc}') from exc


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _run(command: list[str]) -> None:
    logger.info('Running: {}', ' '.join(command))
    subprocess.run(command, check=True)


def _write_release(repo_dir: Path) -> None:
    release = repo_dir / 'Release'
    release.write_text(
        'Origin: robot_mindset\n'
        'Label: robot_mindset offline bundle\n'
        'Suite: stable\n'
        'Codename: robot-mindset-offline\n'
        'Architectures: amd64 all\n'
        'Components: main\n'
        'Description: robot_mindset offline APT repository\n'
    )


def _build_repo(repo_dir: Path) -> None:
    packages = subprocess.run(
        ['dpkg-scanpackages', 'pool', '/dev/null'],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_dir,
    ).stdout
    (repo_dir / 'Packages').write_text(packages)
    with gzip.open(repo_dir / 'Packages.gz', 'wt') as handle:
        handle.write(packages)
    _write_release(repo_dir)


def _apt_base_args(state_dir: Path, archive_dir: Path, sources_list: Path) -> list[str]:
    return [
        '-o', f'Dir::State={state_dir}',
        '-o', f'Dir::State::lists={state_dir / "lists"}',
        '-o', f'Dir::Cache={archive_dir.parent}',
        '-o', f'Dir::Cache::archives={archive_dir}',
        '-o', f'Dir::Etc::sourcelist={sources_list}',
        '-o', 'Dir::Etc::sourceparts=-',
        '-o', 'APT::Get::List-Cleanup=0',
        '-o', 'Debug::NoLocking=true',
    ]


def _write_ubuntu_sources_list(destination: Path, context: dict) -> str:
    release = _target_ubuntu_release(context)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        '\n'.join([
            f'deb [trusted=yes arch=amd64] http://archive.ubuntu.com/ubuntu {release} main restricted universe multiverse',
            f'deb [trusted=yes arch=amd64] http://archive.ubuntu.com/ubuntu {release}-updates main restricted universe multiverse',
            f'deb [trusted=yes arch=amd64] http://security.ubuntu.com/ubuntu {release}-security main restricted universe multiverse',
            f'deb [trusted=yes arch=amd64] http://archive.ubuntu.com/ubuntu {release}-backports main restricted universe multiverse',
            '',
        ])
    )
    return release


def _lists_stamp_path(state_dir: Path) -> Path:
    return state_dir / 'lists' / '.robot_mindset_last_update'


def _should_refresh_package_lists(state_dir: Path) -> bool:
    stamp_path = _lists_stamp_path(state_dir)
    if not stamp_path.exists():
        return True
    age_seconds = time.time() - stamp_path.stat().st_mtime
    return age_seconds > APT_LIST_MAX_AGE_SECONDS


def _mark_package_lists_refreshed(state_dir: Path) -> None:
    stamp_path = _lists_stamp_path(state_dir)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(str(int(time.time())))


def _resolve_cache_dir(context: dict, cache_dir: Path | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir)
    release = _target_ubuntu_release(context)
    image_name = str(context.get('image', 'ubuntu')).replace('.iso', '')
    return DEFAULT_CACHE_ROOT / release / image_name


def prepare_offline_bundle(seed_data_dir: Path, context: dict, cache_dir: Path | None = None) -> Path:
    manifest = _load_manifest()
    seed_data_dir = Path(seed_data_dir)
    cache_dir = _resolve_cache_dir(context, cache_dir)

    offline_root = seed_data_dir / 'offline'
    repo_dir = offline_root / 'repo'
    pool_dir = repo_dir / 'pool'
    realtime_dir = offline_root / 'realtime'
    direct_dir = cache_dir / 'direct'
    archive_dir = cache_dir / 'archives'
    apt_state_dir = cache_dir / 'apt-state'
    sources_list = cache_dir / 'sources.list'
    realtime_cache_dir = cache_dir / 'realtime'

    shutil.rmtree(repo_dir, ignore_errors=True)
    shutil.rmtree(realtime_dir, ignore_errors=True)
    pool_dir.mkdir(parents=True, exist_ok=True)
    realtime_dir.mkdir(parents=True, exist_ok=True)
    direct_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    realtime_cache_dir.mkdir(parents=True, exist_ok=True)
    (apt_state_dir / 'lists' / 'partial').mkdir(parents=True, exist_ok=True)

    release = _write_ubuntu_sources_list(sources_list, context)
    logger.info('Preparing offline bundle for Ubuntu release {} using cache {}', release, cache_dir)

    packages = []
    packages.extend(manifest.get('apt_packages', {}).get('bootstrap', []))
    packages.extend(manifest.get('apt_packages', {}).get('role_packages', []))
    packages.extend(context.get('autoinstall', {}).get('packages', []))
    packages = _dedupe(packages)

    direct_debs: list[Path] = []
    for item in manifest.get('direct_debs', []):
        destination = direct_dir / item['filename']
        _download(item['url'], destination)
        direct_debs.append(destination)
        _copy_file(destination, pool_dir / destination.name)

    linux_kernel = context.get('linux_kernel', {})
    realtime = linux_kernel.get('realtime', {}) if isinstance(linux_kernel, dict) else {}
    if realtime.get('enable'):
        version_major = realtime.get('version_major', 6)
        version_minor = realtime.get('version_minor', 8)
        version_patch = realtime.get('version_patch', 2)
        version_rt = realtime.get('version_rt', 11)
        version = f'{version_major}.{version_minor}.{version_patch}'
        version_with_rt = f'{version}-rt{version_rt}'
        kernel_url = f'https://cdn.kernel.org/pub/linux/kernel/v{version_major}.x/linux-{version}.tar.xz'
        patch_url = f'https://cdn.kernel.org/pub/linux/kernel/projects/rt/{version_major}.{version_minor}/patch-{version_with_rt}.patch.xz'
        kernel_cache_path = realtime_cache_dir / f'linux-{version}.tar.xz'
        patch_cache_path = realtime_cache_dir / f'patch-{version_with_rt}.patch.xz'
        _download(kernel_url, kernel_cache_path)
        _download(patch_url, patch_cache_path)
        _copy_file(kernel_cache_path, realtime_dir / kernel_cache_path.name)
        _copy_file(patch_cache_path, realtime_dir / patch_cache_path.name)

    if packages or direct_debs:
        apt_base_args = _apt_base_args(apt_state_dir, archive_dir, sources_list)
        command = [
            'apt-get',
            '--yes',
            *apt_base_args,
            '--download-only',
            'install',
            *packages,
            *[str(item) for item in direct_debs],
        ]
        if _should_refresh_package_lists(apt_state_dir):
            _run(['apt-get', *apt_base_args, 'update'])
            _mark_package_lists_refreshed(apt_state_dir)
        else:
            logger.info('Reusing cached Ubuntu package lists from {}', apt_state_dir)
        _run(command)

    for deb in archive_dir.glob('*.deb'):
        _copy_file(deb, pool_dir / deb.name)

    _build_repo(repo_dir)
    logger.info('Offline bundle prepared at {} using cache {}', offline_root, cache_dir)
    return offline_root
