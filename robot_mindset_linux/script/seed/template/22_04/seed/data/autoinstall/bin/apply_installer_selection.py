#!/usr/bin/env python3
"""Apply installer-time selections to the extracted target payload."""
import argparse
import json
import shutil
from pathlib import Path

import yaml


DEFAULT_SELECTION_PATH = Path('/autoinstall-working/robot_mindset_installer_selection.json')


def log(message):
    print(f'[robot-mindset-selection] {message}', flush=True)


def load_selection(selection_path: str) -> dict:
    path = Path(selection_path)
    if not path.exists():
        log(f'No installer selection found at {path}; nothing to apply')
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def sanitize_nameservers(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


def write_authorized_keys(target_root: Path, selection: dict) -> None:
    keys = (
        selection.get('software', {})
        .get('ssh', {})
        .get('authorized_keys', [])
    )
    destination = target_root / 'data/user/ssh/authorized_keys'
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = ''.join(f'{str(key).rstrip()}\n' for key in keys if str(key).strip())
    destination.write_text(content, encoding='utf-8')
    log(f'Wrote authorized_keys to {destination}')


def write_sudoers(target_root: Path, selection: dict) -> None:
    username = selection.get('identity', {}).get('username', '').strip()
    sudoers_dir = target_root / 'data/user/sudoers.d'
    sudoers_dir.mkdir(parents=True, exist_ok=True)
    for path in sudoers_dir.iterdir():
        if path.is_file():
            path.unlink()
    if not username:
        log('No username in selection; skipped sudoers rewrite')
        return
    destination = sudoers_dir / username
    destination.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n', encoding='utf-8')
    log(f'Wrote sudoers entry to {destination}')


def build_network_role(item: dict) -> dict | None:
    if not bool(item.get('enabled', True)):
        return None
    name = item.get('set_name') or item.get('set-name') or item.get('name') or item.get('interface_name')
    if not name:
        return None
    interface_name = item.get('set_name') or item.get('set-name') or name
    role = {
        'role': 'NIC',
        'network_name': name,
        'ethernet_interface_name': interface_name,
        'auto_connect': True,
    }
    if bool(item.get('dhcp4', True)):
        role['method4'] = 'auto'
    else:
        address = item.get('address') or item.get('ipv4')
        gateway = item.get('gateway4') or item.get('gateway')
        nameservers = sanitize_nameservers(item.get('nameservers'))
        if address:
            role['ipv4'] = address
        if gateway:
            role['gateway4'] = gateway
        if nameservers:
            role['nameservers'] = nameservers
    return role


def build_realtime_role(selection: dict) -> dict | None:
    realtime = (
        selection.get('software', {})
        .get('linux_kernel', {})
        .get('realtime', {})
    )
    if not realtime.get('enable'):
        return None
    return {
        'role': 'realtime-patch',
        'vars': {
            'version_major': int(realtime.get('version_major', 6)),
            'version_minor': int(realtime.get('version_minor', 8)),
            'version_patch': int(realtime.get('version_patch', 2)),
            'version_rt': int(realtime.get('version_rt', 11)),
            'working_dir': '/robot_mindset/linux_kernel',
        },
    }


def update_playbook(target_root: Path, selection: dict) -> None:
    playbook_path = target_root / 'data/ansible/playbook.yml'
    payload = yaml.safe_load(playbook_path.read_text(encoding='utf-8')) or []
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f'Unexpected playbook structure in {playbook_path}')
    play = payload[0]
    roles = play.get('roles') or []
    base_roles = []
    for role in roles:
        role_name = role.get('role') if isinstance(role, dict) else role
        if role_name in {'NIC', 'realtime-patch'}:
            continue
        base_roles.append(role)

    dynamic_roles = []
    for item in selection.get('networks') or []:
        role = build_network_role(item)
        if role:
            dynamic_roles.append(role)

    realtime_role = build_realtime_role(selection)
    if realtime_role:
        dynamic_roles.append(realtime_role)

    play['roles'] = base_roles + dynamic_roles
    playbook_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
    log(f'Updated playbook at {playbook_path}')


def copy_selection_debug(target_root: Path, selection_path: str) -> None:
    source = Path(selection_path)
    if not source.exists():
        return
    destination = target_root / 'installer-selection.json'
    shutil.copy2(source, destination)
    log(f'Copied selection debug file to {destination}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Apply installer UI selections to the extracted target payload')
    parser.add_argument('--selection-file', default=str(DEFAULT_SELECTION_PATH))
    parser.add_argument('--target-root', default='/target/robot_mindset')
    args = parser.parse_args()

    selection = load_selection(args.selection_file)
    if not selection:
        return

    target_root = Path(args.target_root)
    if not target_root.exists():
        raise RuntimeError(f'Target root does not exist: {target_root}')

    write_authorized_keys(target_root, selection)
    write_sudoers(target_root, selection)
    update_playbook(target_root, selection)
    copy_selection_debug(target_root, args.selection_file)


if __name__ == '__main__':
    main()
