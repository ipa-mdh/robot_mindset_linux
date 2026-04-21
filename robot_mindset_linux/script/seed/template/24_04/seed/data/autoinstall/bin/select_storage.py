#!/usr/bin/env python3
"""Select an installation target for Ubuntu autoinstall without overwriting existing partitions."""
import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config.json'
DEFAULT_SELECTION_PATH = Path('/autoinstall-working/robot_mindset_installer_selection.json')
ALIGNMENT_BYTES = 1048576  # 1 MiB alignment for new partitions


class StoragePlannerError(RuntimeError):
    """Raised when storage selection cannot continue safely."""


def log(message):
    """Write verbose diagnostic output to stderr so Subiquity captures it."""
    print(f'[robot-mindset] {message}', file=sys.stderr)


def fail(message: str):
    """Print an error message and exit."""
    log(message)
    raise StoragePlannerError(message)


def bytes_to_gib(value):
    return round(value / float(1024 ** 3), 2)


def summarize_region(region):
    if not region:
        return 'none'
    return (
        f"start={region['start']} end={region['end']} "
        f"size={region['size']}B ({bytes_to_gib(region['size'])} GiB)"
    )


def run_command(command):
    """Run a command and return stdout."""
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        fail(f'Command not found: {command[0]} ({exc})')
    except subprocess.CalledProcessError as exc:
        fail(f"Command '{' '.join(command)}' failed: {exc.stderr.strip() or exc}")
    return result.stdout


def parse_size(value):
    """Parse sizes like 9G or 1024 into bytes."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper()
    if not text:
        fail('Empty size string encountered in config.json')
    multiplier = 1
    suffix_map = {
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
        'P': 1024 ** 5,
    }
    if text.endswith('B'):
        text = text[:-1]
    suffix = text[-1]
    if suffix in suffix_map:
        multiplier = suffix_map[suffix]
        number = text[:-1]
    else:
        number = text
    try:
        amount = Decimal(number)
    except Exception as exc:
        fail(f"Cannot parse size '{value}': {exc}")
    return int(amount * multiplier)


def load_config():
    """Load installer configuration emitted during ISO rendering."""
    if not CONFIG_PATH.exists():
        fail(f'Missing storage planner config: {CONFIG_PATH}')
    with open(CONFIG_PATH, encoding='utf-8') as handle:
        data = json.load(handle)
    config = {
        'bios_grub_size': parse_size(data.get('bios_grub_size', '4M')),
        'efi_size': parse_size(data.get('efi_size', '1G')),
        'boot_size': parse_size(data.get('boot_size', '4G')),
        'boot_size_text': data.get('boot_size_text', data.get('boot_size', '4G')),
        'boot_label': data.get('boot_label', 'BOOT'),
        'efi_label': data.get('efi_label', 'ESP'),
        'root_label': data.get('root_label', 'root'),
        'filesystem': data.get('filesystem', 'btrfs'),
        'encryption_key': data.get('encryption_key', ''),
        'min_free_bytes': int(data.get('min_free_bytes', 40 * 1024 ** 3)),
        'prefer_ssd': bool(data.get('prefer_ssd', True)),
        'environment': data.get('environment', ''),
        'image': data.get('image', ''),
        'source_id': data.get('source_id', ''),
        'ssh_authorized_keys': data.get('ssh_authorized_keys', []) or [],
        'linux_kernel_realtime': data.get('linux_kernel_realtime', {}) or {},
    }
    if not config['encryption_key']:
        fail('Encryption key missing in storage planner config.json')
    log(
        'Loaded config: '
        f"boot_size={config['boot_size']}B ({bytes_to_gib(config['boot_size'])} GiB), "
        f"efi_size={config['efi_size']}B ({bytes_to_gib(config['efi_size'])} GiB), "
        f"bios_grub_size={config['bios_grub_size']}B, "
        f"min_free_bytes={config['min_free_bytes']}B ({bytes_to_gib(config['min_free_bytes'])} GiB), "
        f"prefer_ssd={config['prefer_ssd']}"
    )
    return config


def collect_lsblk():
    """Return lsblk JSON output."""
    output = run_command([
        'lsblk',
        '-b',
        '-J',
        '-o',
        'NAME,TYPE,ROTA,SIZE,FSTYPE,MOUNTPOINTS',
    ])
    data = json.loads(output)
    log(f"lsblk returned {len(data.get('blockdevices', []))} blockdevices")
    log(f"lsblk raw: {json.dumps(data, sort_keys=True)}")
    return data.get('blockdevices', [])


def parse_partition_number(name: str):
    """Extract the trailing partition number from a device name."""
    match = re.search(r'(\d+)$', name)
    if match:
        return int(match.group(1))
    return None


def parse_parted_output(output, device_path):
    """Parse machine-readable parted output into table type and free regions."""
    lines = [line.strip().rstrip(';') for line in output.splitlines() if line.strip()]
    free_regions = []
    table_type = None
    for line in lines:
        if line in {'BYT', 'BYT;'}:
            continue
        raw_parts = line.split(':')
        parts = [part.rstrip(';') for part in raw_parts]
        if line.startswith(device_path):
            if len(parts) >= 6:
                table_type = parts[5]
            continue
        if len(parts) < 4:
            continue
        try:
            start = int(parts[1][:-1])
            end = int(parts[2][:-1])
            size = int(parts[3][:-1])
        except ValueError:
            continue
        marker_fields = {field for field in parts if field}
        if 'free' in marker_fields:
            free_regions.append({'start': start, 'end': end, 'size': size})
    return table_type or 'unknown', free_regions


def parse_parted(device_path, disk_size):
    """Use parted to identify existing free regions on the disk."""
    command = ['parted', '-m', device_path, 'unit', 'B', 'print', 'free']
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
        )
        output = result.stdout
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired:
        log(f"parted timed out for {device_path}; skipping this disk for safety")
        return 'unknown', [], '', 'error'
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ''
        log(f"parted stderr for {device_path}: {stderr.strip() or '<empty>'}")
        stderr_lower = stderr.lower()
        if 'unrecognised disk label' in stderr_lower or 'unrecognized disk label' in stderr_lower:
            log(f'{device_path}: no partition table detected by parted; marking disk as blank')
            return 'unknown', [{'start': 0, 'end': disk_size, 'size': disk_size}], '', 'blank'
        log(f"parted failed for {device_path}; skipping this disk for safety")
        return 'unknown', [], '', 'error'

    if stderr.strip():
        log(f'parted stderr for {device_path}: {stderr.strip()}')
    log(f"parted raw for {device_path}: {output.strip() or '<empty>'}")

    table_type, free_regions = parse_parted_output(output, device_path)
    if not free_regions and table_type in {None, 'unknown'}:
        log(f'{device_path}: unknown partition table with no free rows; treating disk as blank')
        return 'unknown', [{'start': 0, 'end': disk_size, 'size': disk_size}], output, 'blank'
    return table_type, free_regions, output, 'ok'


def is_whole_disk_region(region, disk_size):
    if not region:
        return False
    start = region.get('start', 0)
    end = region.get('end', 0)
    size = region.get('size', 0)
    leading_gap_ok = start <= ALIGNMENT_BYTES
    trailing_gap_ok = max(disk_size - end, 0) <= ALIGNMENT_BYTES
    large_enough = size >= max(disk_size - (2 * ALIGNMENT_BYTES), 0)
    return leading_gap_ok and trailing_gap_ok and large_enough


def gather_disks(min_free_bytes):
    """Collect relevant metadata for each concrete disk device."""
    disks = []
    for entry in collect_lsblk():
        if entry.get('type') != 'disk':
            continue
        name = entry.get('name')
        if not name or name.startswith('loop') or name.startswith('ram'):
            continue
        size = int(entry.get('size') or 0)
        if size <= 0:
            continue
        device_path = f'/dev/{name}'
        partitions = []
        children = entry.get('children') or []
        for child in children:
            if child.get('type') != 'part':
                continue
            number = parse_partition_number(child.get('name', ''))
            partitions.append({
                'name': child.get('name'),
                'number': number,
                'size': int(child.get('size') or 0),
                'fstype': child.get('fstype'),
            })

        table_type, free_regions, parted_output, parted_state = parse_parted(device_path, size)
        whole_disk_allowed = False
        if parted_state == 'error':
            free_regions = []
            log(f'{device_path}: ignoring disk because parted could not verify its layout safely')
        elif partitions and parted_state == 'blank':
            free_regions = []
            log(f'{device_path}: lsblk reported partitions but parted reported a blank disk; skipping for safety')
        elif not partitions and parted_state == 'blank':
            whole_disk_allowed = True
            log(f'{device_path}: verified as an empty disk by parted')
        elif not partitions and is_whole_disk_region(max(free_regions, key=lambda region: region['size']) if free_regions else None, size):
            whole_disk_allowed = True
            log(f'{device_path}: no partitions reported and parted returned a whole-disk free region')
        elif not partitions:
            free_regions = []
            log(f'{device_path}: no partitions reported by lsblk but parted did not confirm a blank disk; skipping whole-disk install for safety')

        largest_free = max(free_regions, key=lambda region: region['size']) if free_regions else None
        disk = {
            'name': name,
            'path': device_path,
            'size': size,
            'is_ssd': str(entry.get('rota', '1')) == '0',
            'partitions': partitions,
            'ptable': table_type,
            'free_regions': free_regions,
            'largest_free': largest_free,
            'parted_output': parted_output,
            'parted_state': parted_state,
            'whole_disk_allowed': whole_disk_allowed,
        }
        disks.append(disk)
        log(
            f'Detected disk {device_path}: size={size}B ({bytes_to_gib(size)} GiB), '
            f"ssd={disk['is_ssd']}, ptable={table_type}, partitions={len(partitions)}, "
            f"parted_state={parted_state}, whole_disk_allowed={whole_disk_allowed}, "
            f"largest_free={summarize_region(largest_free)}"
        )
        for partition in partitions:
            log(
                f"  partition {partition['name']}: number={partition['number']} "
                f"size={partition['size']}B ({bytes_to_gib(partition['size'])} GiB) "
                f"fstype={partition['fstype']}"
            )
        for index, region in enumerate(free_regions, start=1):
            log(f'  free region {index}: {summarize_region(region)}')
    return disks


def selection_sort_key(disk, prefer_ssd=True):
    """Prefer SSDs, then larger disks, then larger free extents."""
    return (
        1 if (prefer_ssd and disk.get('is_ssd')) else 0,
        disk.get('size', 0),
        disk.get('largest_free', {}).get('size', 0),
    )


def candidate_id(path, scenario):
    return f'{scenario}:{path}'


def serialize_candidate(disk):
    region = disk.get('largest_free') or {}
    return {
        'id': candidate_id(disk['path'], disk['scenario']),
        'path': disk['path'],
        'name': disk['name'],
        'scenario': disk['scenario'],
        'is_ssd': disk['is_ssd'],
        'disk_size': disk['size'],
        'disk_size_gib': bytes_to_gib(disk['size']),
        'free_region': region,
        'free_region_gib': bytes_to_gib(region.get('size', 0)),
        'partition_count': len(disk.get('partitions', [])),
        'partitions': disk.get('partitions', []),
        'sort_key': list(selection_sort_key(disk)),
    }


def collect_candidates(disks, min_free_bytes, prefer_ssd=True):
    """Return all eligible installation targets ordered by preference."""
    populated = []
    empty = []
    for disk in disks:
        region = disk.get('largest_free')
        if not region:
            log(f"Skipping {disk['path']}: no free region detected")
            continue
        if disk.get('partitions'):
            if disk.get('ptable') not in {'gpt', 'msdos'}:
                log(f"Skipping {disk['path']}: partitioned disk has unsupported partition table {disk.get('ptable')}")
                continue
            if region.get('size', 0) < min_free_bytes:
                log(
                    f"Skipping {disk['path']}: largest free region {region['size']}B "
                    f"({bytes_to_gib(region['size'])} GiB) is below threshold "
                    f"{min_free_bytes}B ({bytes_to_gib(min_free_bytes)} GiB)"
                )
                continue
            candidate = dict(disk)
            candidate['scenario'] = 'free-space'
            populated.append(candidate)
            log(f"Candidate {disk['path']} classified as free-space install target")
        elif disk.get('whole_disk_allowed'):
            candidate = dict(disk)
            candidate['scenario'] = 'whole-disk'
            empty.append(candidate)
            log(f"Candidate {disk['path']} classified as whole-disk install target")
        else:
            log(f"Skipping {disk['path']}: whole-disk installation is not allowed because the disk layout could not be verified as empty")

    populated.sort(key=lambda disk: selection_sort_key(disk, prefer_ssd=prefer_ssd), reverse=True)
    empty.sort(key=lambda disk: selection_sort_key(disk, prefer_ssd=prefer_ssd), reverse=True)
    return populated + empty


def select_disk(candidates):
    """Choose the best installation candidate."""
    if not candidates:
        return None
    selection = candidates[0]
    log(f"Selected {selection['scenario']} candidate {selection['path']} with region {summarize_region(selection['largest_free'])}")
    return selection


def align_up(value, alignment):
    remainder = value % alignment
    if remainder == 0:
        return value
    return value + (alignment - remainder)


def next_partition_number(disk):
    numbers = [part['number'] for part in disk.get('partitions', []) if part.get('number')]
    if not numbers:
        return 1
    return max(numbers) + 1


def build_plan(disk, config):
    """Build the desired curtin storage config for the selected disk."""
    scenario = disk.get('scenario')
    if not scenario:
        fail('Internal error: disk selection missing scenario')

    disk_id = f"disk-{disk['name']}"
    region = disk.get('largest_free')
    if not region:
        fail('Selected disk reports no free regions')

    if scenario == 'whole-disk':
        ptable = 'gpt'
    else:
        ptable = disk.get('ptable')
        if ptable not in {'gpt', 'msdos'}:
            fail(f"Selected populated disk has unsupported partition table: {ptable}")

    plan = {
        'disk_id': disk_id,
        'disk_path': disk['path'],
        'ptable': ptable,
        'scenario': scenario,
        'partitions': [],
        'region': region,
    }

    boot_size = config['boot_size']
    efi_size = config['efi_size']
    bios_size = config['bios_grub_size'] if ptable == 'gpt' else 0

    free_start = region['start']
    free_end = region['end']
    aligned_start = align_up(free_start, ALIGNMENT_BYTES)
    available = free_end - aligned_start

    required_for_fixed_parts = bios_size + efi_size + boot_size
    log(
        f"Building plan for {disk['path']}: scenario={scenario}, free_start={free_start}, "
        f"aligned_start={aligned_start}, free_end={free_end}, available={available}B "
        f"({bytes_to_gib(max(available, 0))} GiB), fixed_partitions={required_for_fixed_parts}B"
    )

    if available <= required_for_fixed_parts:
        fail(
            'Selected disk/free space is too small for the required fixed partitions. '
            f'Need more than {required_for_fixed_parts} bytes.'
        )

    if scenario == 'free-space':
        root_size = available - required_for_fixed_parts
    else:
        root_size = -1

    number = next_partition_number(disk) if scenario == 'free-space' else 1

    def next_number():
        nonlocal number
        current = number
        number += 1
        return current

    def allocate(size):
        nonlocal aligned_start
        offset = aligned_start
        aligned_start += size
        return offset

    partitions = []

    if bios_size > 0:
        entry = {
            'id': f'{disk_id}-grub',
            'type': 'partition',
            'device': disk_id,
            'size': bios_size,
            'number': next_number(),
            'grub_device': False,
            'flag': 'bios_grub',
            'wipe': 'superblock',
            'preserve': False,
        }
        if scenario == 'free-space':
            entry['offset'] = allocate(bios_size)
        partitions.append(entry)

    efi_entry = {
        'id': f'{disk_id}-efi',
        'type': 'partition',
        'device': disk_id,
        'size': efi_size,
        'number': next_number(),
        'grub_device': 'UEFI',
        'flag': 'boot',
        'wipe': 'superblock',
        'preserve': False,
    }
    if scenario == 'free-space':
        efi_entry['offset'] = allocate(efi_size)
    partitions.append(efi_entry)

    boot_entry = {
        'id': f'{disk_id}-boot',
        'type': 'partition',
        'device': disk_id,
        'size': boot_size,
        'number': next_number(),
        'grub_device': False,
        'wipe': 'superblock',
        'preserve': False,
    }
    if scenario == 'free-space':
        boot_entry['offset'] = allocate(boot_size)
    partitions.append(boot_entry)

    crypt_entry = {
        'id': f'{disk_id}-crypt',
        'type': 'partition',
        'device': disk_id,
        'size': root_size if root_size > 0 else -1,
        'number': next_number(),
        'grub_device': False,
        'wipe': 'superblock',
        'preserve': False,
    }
    if scenario == 'free-space':
        crypt_entry['offset'] = allocate(root_size)
    partitions.append(crypt_entry)

    plan['partitions'] = partitions
    plan['root_partition_size'] = root_size
    plan['requires_offsets'] = scenario == 'free-space'
    plan['disk_preserve'] = scenario == 'free-space'
    plan['dm_id'] = f'{disk_id}-cryptmap'
    plan['root_fmt_id'] = f'{disk_id}-root-fmt'

    log(f'Plan root partition size: {root_size}')
    return plan


def build_storage_config(plan, config):
    """Build the curtin storage config structure."""
    disk_preserve = plan.get('disk_preserve', False)
    disk_id = plan['disk_id']
    storage = {
        'version': 1,
        'config': [
            {
                'type': 'disk',
                'id': disk_id,
                'ptable': plan['ptable'],
                'path': plan['disk_path'],
                'preserve': disk_preserve,
                'grub_device': True,
            }
        ],
    }
    if not disk_preserve:
        storage['config'][0]['wipe'] = 'superblock-recursive'

    for part in plan['partitions']:
        partition_entry = {
            'type': 'partition',
            'id': part['id'],
            'device': disk_id,
            'number': part['number'],
            'size': part['size'],
            'wipe': part['wipe'],
            'grub_device': part['grub_device'],
            'preserve': part['preserve'],
        }
        if part.get('flag'):
            partition_entry['flag'] = part['flag']
        if plan['requires_offsets'] and part.get('offset') is not None:
            partition_entry['offset'] = part['offset']
        storage['config'].append(partition_entry)

        if part['id'].endswith('-efi'):
            storage['config'].extend([
                {
                    'type': 'format',
                    'id': f"{part['id']}-format",
                    'volume': part['id'],
                    'fstype': 'fat32',
                    'label': config['efi_label'],
                },
                {
                    'type': 'mount',
                    'id': f"{part['id']}-mount",
                    'device': f"{part['id']}-format",
                    'path': '/boot/efi',
                },
            ])
        elif part['id'].endswith('-boot'):
            storage['config'].extend([
                {
                    'type': 'format',
                    'id': f"{part['id']}-format",
                    'volume': part['id'],
                    'fstype': 'ext4',
                    'label': config['boot_label'],
                },
                {
                    'type': 'mount',
                    'id': f"{part['id']}-mount",
                    'device': f"{part['id']}-format",
                    'path': '/boot',
                },
            ])
        elif part['id'].endswith('-crypt'):
            storage['config'].extend([
                {
                    'type': 'dm_crypt',
                    'id': plan['dm_id'],
                    'volume': part['id'],
                    'dm_name': 'crypt-root',
                    'key': config['encryption_key'],
                },
                {
                    'type': 'format',
                    'id': plan['root_fmt_id'],
                    'volume': plan['dm_id'],
                    'fstype': config['filesystem'],
                    'label': config['root_label'],
                },
                {
                    'type': 'mount',
                    'id': 'root-mount',
                    'device': plan['root_fmt_id'],
                    'path': '/',
                },
            ])
    log(f"Rendered {len(storage['config'])} storage config entries")
    return storage


def sanitize_nameservers(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


def build_network_config(selection):
    entries = (selection or {}).get('networks') or []
    if not entries:
        return None

    network = {'version': 2, 'ethernets': {}}
    for item in entries:
        if not bool(item.get('enabled', True)):
            continue
        name = (
            item.get('set_name')
            or item.get('set-name')
            or item.get('name')
            or item.get('interface_name')
        )
        if not name:
            continue
        dhcp4 = bool(item.get('dhcp4', True))
        interface = {'dhcp4': dhcp4}
        macaddress = item.get('macaddress') or item.get('mac')
        if macaddress:
            interface['match'] = {'macaddress': str(macaddress).strip().lower()}
        interface['set-name'] = item.get('set_name') or item.get('set-name') or name
        if not dhcp4:
            address = item.get('address') or item.get('ipv4')
            gateway = item.get('gateway4') or item.get('gateway')
            nameservers = sanitize_nameservers(item.get('nameservers'))
            if address:
                interface['addresses'] = [address]
            if gateway:
                interface['routes'] = [{'to': 'default', 'via': gateway}]
            if nameservers:
                interface['nameservers'] = {'addresses': nameservers}
        network['ethernets'][name] = interface
    return network if network['ethernets'] else None


def read_autoinstall(autoinstall_path):
    path = Path(autoinstall_path)
    if not path.exists():
        fail(f'Cannot find autoinstall config at {autoinstall_path}')

    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        fail(f'Could not parse {autoinstall_path} as YAML: {exc}')

    if not isinstance(data, dict):
        fail(f'Unexpected top-level YAML type in {autoinstall_path}: {type(data).__name__}')

    return data.get('autoinstall') if isinstance(data.get('autoinstall'), dict) else data


def extract_identity_entry(autoinstall_path):
    autoinstall = read_autoinstall(autoinstall_path)
    identity = autoinstall.get('identity', {}) or {}
    return {
        'hostname': identity.get('hostname', ''),
        'realname': identity.get('realname', ''),
        'username': identity.get('username', ''),
        'password': identity.get('password', ''),
    }


def build_identity_config(selection, autoinstall_path):
    current_identity = extract_identity_entry(autoinstall_path)
    requested_identity = (selection or {}).get('identity') or {}
    identity = dict(current_identity)
    for key in ('hostname', 'realname', 'username', 'password'):
        value = requested_identity.get(key)
        if value:
            identity[key] = value
    return identity


def overlay_config_with_selection(config, selection):
    merged = dict(config)
    storage = ((selection or {}).get('hardware') or {}).get('storage') or {}
    password = storage.get('password')
    if password:
        merged['encryption_key'] = password
    boot_size_text = storage.get('boot_size')
    if boot_size_text:
        merged['boot_size_text'] = boot_size_text
        merged['boot_size'] = parse_size(boot_size_text)
    return merged


def update_autoinstall(autoinstall_path, storage_config, network_config=None, identity_config=None):
    """Replace storage/network/identity blocks in /autoinstall.yaml using YAML-aware editing."""
    path = Path(autoinstall_path)
    if not path.exists():
        fail(f'Cannot find autoinstall config at {autoinstall_path}')

    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        fail(f'Could not parse {autoinstall_path} as YAML: {exc}')

    if not isinstance(data, dict):
        fail(f'Unexpected top-level YAML type in {autoinstall_path}: {type(data).__name__}')

    target = data.get('autoinstall') if isinstance(data.get('autoinstall'), dict) else data
    target['storage'] = storage_config
    if network_config:
        target['network'] = network_config
    if identity_config:
        target['identity'] = identity_config

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    log(f'Updated autoinstall file at {autoinstall_path} using yaml-rewrite')


def load_selection(selection_path):
    path = Path(selection_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        fail(f'Could not parse selection file {selection_path}: {exc}')
    log(f'Loaded installer selection from {selection_path}: {json.dumps(data, sort_keys=True)}')
    return data


def choose_candidate(candidates, selection):
    selected_id = (selection or {}).get('selected_storage_id')
    if selected_id:
        for candidate in candidates:
            if candidate_id(candidate['path'], candidate['scenario']) == selected_id:
                log(f'Using user-selected storage candidate {selected_id}')
                return candidate
        fail(f'User-selected storage candidate {selected_id} is not available anymore')

    selected_storage = (selection or {}).get('selected_storage') or {}
    selected_path = selected_storage.get('path')
    selected_scenario = selected_storage.get('scenario')
    if selected_path and selected_scenario:
        expected_id = candidate_id(selected_path, selected_scenario)
        for candidate in candidates:
            if candidate_id(candidate['path'], candidate['scenario']) == expected_id:
                log(f'Using user-selected storage candidate {expected_id}')
                return candidate
        fail(f'User-selected storage candidate {expected_id} is not available anymore')

    return select_disk(candidates)


def write_debug(plan, disks, candidates, selection):
    """Persist the decision for troubleshooting."""
    debug_dir = Path('/autoinstall-working')
    debug_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        'scenario': plan.get('scenario'),
        'disk': {
            'name': plan.get('disk_id'),
            'path': plan.get('disk_path'),
            'ptable': plan.get('ptable'),
        },
        'free_region': plan.get('region'),
        'partitions': plan.get('partitions'),
        'root_partition_size': plan.get('root_partition_size'),
        'detected_disks': disks,
        'candidates': [serialize_candidate(item) for item in candidates],
        'selection': selection,
    }
    debug_path = debug_dir / 'robot_mindset_storage_plan.json'
    with open(debug_path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2)
    log(f'Wrote debug plan to {debug_path}')


def main():
    parser = argparse.ArgumentParser(description='Select storage layout for Robot Mindset autoinstall')
    parser.add_argument('--autoinstall', default='/autoinstall.yaml', help='Path to the autoinstall YAML file to rewrite')
    parser.add_argument('--selection-file', default=str(DEFAULT_SELECTION_PATH), help='Optional user selection JSON produced by the installer UI')
    args = parser.parse_args()

    config = load_config()
    selection = load_selection(args.selection_file)
    effective_config = overlay_config_with_selection(config, selection)

    disks = gather_disks(effective_config["min_free_bytes"])
    if not disks:
        fail('No disk devices detected by lsblk')

    candidates = collect_candidates(disks, effective_config['min_free_bytes'], prefer_ssd=effective_config['prefer_ssd'])
    if not candidates:
        fail('No suitable disk or free space was found. At least 40GiB of unformatted space is required on an existing disk or an empty target disk must be available.')

    chosen_candidate = choose_candidate(candidates, selection)
    if not chosen_candidate:
        fail('No storage candidate could be selected')

    plan = build_plan(chosen_candidate, effective_config)
    storage_config = build_storage_config(plan, effective_config)
    network_config = build_network_config(selection)
    identity_config = build_identity_config(selection, args.autoinstall)
    update_autoinstall(args.autoinstall, storage_config, network_config=network_config, identity_config=identity_config)
    write_debug(plan, disks, candidates, selection)
    log(f"Selected {chosen_candidate['path']} using scenario {plan['scenario']}")


if __name__ == '__main__':
    try:
        main()
    except StoragePlannerError:
        sys.exit(1)
    except Exception as exc:
        log(f'Unexpected failure: {exc}')
        sys.exit(1)
