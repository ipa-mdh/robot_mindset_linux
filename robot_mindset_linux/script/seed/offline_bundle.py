from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tarfile
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
BUNDLE_FORMAT_VERSION = 2

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


def _archive_repo(repo_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, 'w') as tar:
        for entry in sorted(repo_dir.rglob('*')):
            tar.add(entry, arcname=entry.relative_to(repo_dir), recursive=False)


def _files_fingerprint(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        stat_result = path.stat()
        digest.update(str(path.name).encode('utf-8'))
        digest.update(str(stat_result.st_size).encode('utf-8'))
        digest.update(str(stat_result.st_mtime_ns).encode('utf-8'))
    return digest.hexdigest()


def _bundle_signature(manifest: dict, context: dict, packages: list[str], direct_debs: list[Path], archive_dir: Path, realtime_files: list[Path]) -> str:
    payload = {
        'bundle_format_version': BUNDLE_FORMAT_VERSION,
        'image': context.get('image'),
        'ubuntu_release': _target_ubuntu_release(context),
        'packages': packages,
        'manifest': manifest,
        'direct_debs': _files_fingerprint(direct_debs),
        'archive_debs': _files_fingerprint(archive_dir.glob('*.deb')),
        'realtime_files': _files_fingerprint(realtime_files),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def _apt_base_args(state_dir: Path, archive_dir: Path, sources_list: Path) -> list[str]:
    status_file = state_dir / 'status'
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.touch(exist_ok=True)
    return [
        '-o', f'Dir::State={state_dir}',
        '-o', f'Dir::State::status={status_file}',
        '-o', f'Dir::State::lists={state_dir / "lists"}',
        '-o', f'Dir::Cache={archive_dir.parent}',
        '-o', f'Dir::Cache::archives={archive_dir}',
        '-o', f'Dir::Etc::sourcelist={sources_list}',
        '-o', 'Dir::Etc::sourceparts=-',
        '-o', 'APT::Get::List-Cleanup=0',
        '-o', 'Debug::NoLocking=true',
        '-o', 'APT::Architecture=amd64',
        '-o', 'Acquire::AllowInsecureRepositories=true',
        '-o', 'Acquire::AllowDowngradeToInsecureRepositories=true',
        '-o', 'APT::Get::AllowUnauthenticated=true',
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


def _package_candidate(package: str, apt_base_args: list[str]) -> str:
    result = subprocess.run(
        ['apt-cache', *apt_base_args, 'policy', package],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith('Candidate:'):
            return stripped.split(':', 1)[1].strip()
    return '(none)'


def _validate_packages_available(packages: list[str], apt_base_args: list[str], release: str) -> None:
    missing = []
    for package in packages:
        candidate = _package_candidate(package, apt_base_args)
        if candidate in {'', '(none)'}:
            missing.append(package)
    if missing:
        raise RuntimeError(
            f'offline bundle packages unavailable for Ubuntu {release}: ' + ', '.join(missing)
        )


def _validate_direct_debs(direct_debs: list[Path]) -> None:
    invalid = []
    for deb in direct_debs:
        result = subprocess.run(
            ['dpkg-deb', '--field', str(deb), 'Package', 'Architecture'],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = {}
        for line in result.stdout.splitlines():
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip()
        package_name = metadata.get('Package', deb.name)
        architecture = metadata.get('Architecture', '')
        if architecture not in {'amd64', 'all'}:
            invalid.append(f'{package_name} ({architecture or "unknown"})')
    if invalid:
        raise RuntimeError('offline bundle direct debs have unsupported architectures: ' + ', '.join(invalid))


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
    repo_tar_path = offline_root / 'repo.tar'
    realtime_dir = offline_root / 'realtime'
    direct_dir = cache_dir / 'direct'
    archive_dir = cache_dir / 'archives'
    apt_state_dir = cache_dir / 'apt-state'
    sources_list = cache_dir / 'sources.list'
    realtime_cache_dir = cache_dir / 'realtime'
    cached_repo_tar_path = cache_dir / 'repo.tar'
    cached_repo_signature_path = cache_dir / 'repo.tar.signature'

    shutil.rmtree(repo_dir, ignore_errors=True)
    shutil.rmtree(realtime_dir, ignore_errors=True)
    repo_tar_path.unlink(missing_ok=True)
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
    _validate_direct_debs(direct_debs)

    linux_kernel = context.get('linux_kernel', {})
    realtime = linux_kernel.get('realtime', {}) if isinstance(linux_kernel, dict) else {}
    realtime_files: list[Path] = []
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
        realtime_files.extend([kernel_cache_path, patch_cache_path])

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
        _validate_packages_available(packages, apt_base_args, release)
        _run(command)

    bundle_signature = _bundle_signature(manifest, context, packages, direct_debs, archive_dir, realtime_files)
    cached_signature = cached_repo_signature_path.read_text().strip() if cached_repo_signature_path.exists() else ''
    if cached_repo_tar_path.exists() and cached_signature == bundle_signature:
        logger.info('Reusing cached offline repo archive {}', cached_repo_tar_path)
        _copy_file(cached_repo_tar_path, repo_tar_path)
        logger.info('Offline bundle prepared at {} using cache {}', offline_root, cache_dir)
        return offline_root

    pool_dir.mkdir(parents=True, exist_ok=True)
    for deb in direct_debs:
        _copy_file(deb, pool_dir / deb.name)
    for deb in archive_dir.glob('*.deb'):
        _copy_file(deb, pool_dir / deb.name)

    _build_repo(repo_dir)
    _archive_repo(repo_dir, repo_tar_path)
    _copy_file(repo_tar_path, cached_repo_tar_path)
    cached_repo_signature_path.write_text(bundle_signature)
    shutil.rmtree(repo_dir)
    logger.info('Offline bundle prepared at {} using cache {}', offline_root, cache_dir)
    return offline_root
