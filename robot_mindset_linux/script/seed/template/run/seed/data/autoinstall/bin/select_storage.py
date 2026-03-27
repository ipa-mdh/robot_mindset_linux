#!/usr/bin/env python3
"""Select an installation target for Ubuntu autoinstall without overwriting existing partitions."""
import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

MARKER_START = "# robot_mindset_storage_begin"
MARKER_END = "# robot_mindset_storage_end"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"
ALIGNMENT_BYTES = 1048576  # 1 MiB alignment for new partitions


class StoragePlannerError(RuntimeError):
    """Raised when storage selection cannot continue safely."""


def fail(message: str, exit_code: int = 1):
    """Print an error message and exit."""
    print(f"[robot-mindset] {message}", file=sys.stderr)
    raise StoragePlannerError(message)


def run_command(command):
    """Run a command and return stdout."""
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        fail(f"Command not found: {command[0]} ({exc})")
    except subprocess.CalledProcessError as exc:
        fail(f"Command '{' '.join(command)}' failed: {exc.stderr.strip() or exc}")
    return result.stdout


def parse_size(value):
    """Parse sizes like 9G or 1024 into bytes."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper()
    if not text:
        fail("Empty size string encountered in config.json")
    multiplier = 1
    suffix_map = {
        "K": 1024,
        "M": 1024 ** 2,
        "G": 1024 ** 3,
        "T": 1024 ** 4,
        "P": 1024 ** 5,
    }
    if text.endswith("B"):
        text = text[:-1]
    suffix = text[-1]
    if suffix in suffix_map:
        multiplier = suffix_map[suffix]
        number = text[:-1]
    else:
        number = text
    try:
        amount = Decimal(number)
    except Exception as exc:  # pragma: no cover - best effort parsing
        fail(f"Cannot parse size '{value}': {exc}")
    return int(amount * multiplier)


def load_config():
    """Load installer configuration emitted during ISO rendering."""
    if not CONFIG_PATH.exists():
        fail(f"Missing storage planner config: {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    config = {
        "bios_grub_size": parse_size(data.get("bios_grub_size", "4M")),
        "efi_size": parse_size(data.get("efi_size", "1G")),
        "boot_size": parse_size(data.get("boot_size", "4G")),
        "boot_label": data.get("boot_label", "BOOT"),
        "efi_label": data.get("efi_label", "ESP"),
        "root_label": data.get("root_label", "root"),
        "filesystem": data.get("filesystem", "btrfs"),
        "encryption_key": data.get("encryption_key", ""),
        "min_free_bytes": int(data.get("min_free_bytes", 40 * 1024 ** 3)),
        "prefer_ssd": bool(data.get("prefer_ssd", True)),
    }
    if not config["encryption_key"]:
        fail("Encryption key missing in storage planner config.json")
    return config


def collect_lsblk():
    """Return lsblk JSON output."""
    output = run_command([
        "lsblk",
        "-b",
        "-J",
        "-o",
        "NAME,TYPE,ROTA,SIZE,FSTYPE,MOUNTPOINTS"
    ])
    data = json.loads(output)
    return data.get("blockdevices", [])


def parse_partition_number(name: str):
    """Extract the trailing partition number from a device name."""
    match = re.search(r"(\d+)$", name)
    if match:
        return int(match.group(1))
    return None


def parse_parted(device_path):
    """Use parted to identify existing free regions on the disk."""
    output = run_command(["parted", "-m", device_path, "unit", "B", "print", "free"])
    lines = [line.strip().rstrip(";") for line in output.splitlines() if line.strip()]
    free_regions = []
    table_type = None
    for line in lines:
        if line == "BYT":
            continue
        if line.startswith(device_path):
            parts = line.split(":")
            if len(parts) >= 6:
                table_type = parts[5]
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        number = parts[0]
        try:
            start = int(parts[1][:-1])
            end = int(parts[2][:-1])
            size = int(parts[3][:-1])
        except ValueError:
            continue
        if number == "free":
            free_regions.append({"start": start, "end": end, "size": size})
    return table_type or "unknown", free_regions


def gather_disks():
    """Collect relevant metadata for each concrete disk device."""
    disks = []
    for entry in collect_lsblk():
        if entry.get("type") != "disk":
            continue
        name = entry.get("name")
        if not name or name.startswith("loop") or name.startswith("ram"):
            continue
        size = int(entry.get("size") or 0)
        if size <= 0:
            continue
        device_path = f"/dev/{name}"
        table_type, free_regions = parse_parted(device_path)
        partitions = []
        children = entry.get("children") or []
        for child in children:
            if child.get("type") != "part":
                continue
            number = parse_partition_number(child.get("name", ""))
            partitions.append({
                "name": child.get("name"),
                "number": number,
                "size": int(child.get("size") or 0),
                "fstype": child.get("fstype"),
            })
        largest_free = max(free_regions, key=lambda region: region["size"]) if free_regions else None
        disks.append({
            "name": name,
            "path": device_path,
            "size": size,
            "is_ssd": str(entry.get("rota", "1")) == "0",
            "partitions": partitions,
            "ptable": table_type,
            "free_regions": free_regions,
            "largest_free": largest_free,
        })
    return disks


def select_disk(disks, min_free_bytes, prefer_ssd=True):
    """Choose a disk and free region based on the requirements."""
    def sort_key(disk):
        return (
            1 if (prefer_ssd and disk.get("is_ssd")) else 0,
            disk.get("largest_free", {}).get("size", 0),
            disk.get("size", 0),
        )

    populated = []
    empty = []
    for disk in disks:
        region = disk.get("largest_free")
        if not region or region.get("size", 0) < min_free_bytes:
            continue
        if disk.get("partitions"):
            populated.append(disk)
        else:
            empty.append(disk)

    if populated:
        populated.sort(key=sort_key, reverse=True)
        selection = populated[0]
        selection["scenario"] = "free-space"
        return selection

    if empty:
        empty.sort(key=sort_key, reverse=True)
        selection = empty[0]
        selection["scenario"] = "whole-disk"
        return selection

    return None


def align_up(value, alignment):
    remainder = value % alignment
    if remainder == 0:
        return value
    return value + (alignment - remainder)


def next_partition_number(disk):
    numbers = [part["number"] for part in disk.get("partitions", []) if part.get("number")]
    if not numbers:
        return 1
    return max(numbers) + 1


def build_plan(disk, config):
    """Build the desired curtin storage config for the selected disk."""
    scenario = disk.get("scenario")
    if not scenario:
        fail("Internal error: disk selection missing scenario")

    disk_id = f"disk-{disk['name']}"
    base_alignment = ALIGNMENT_BYTES
    region = disk.get("largest_free")
    if not region:
        fail("Selected disk reports no free regions")

    plan = {
        "disk_id": disk_id,
        "disk_path": disk["path"],
        "ptable": disk.get("ptable", "gpt"),
        "scenario": scenario,
        "partitions": [],
        "region": region,
    }

    boot_size = config["boot_size"]
    efi_size = config["efi_size"]
    bios_size = config["bios_grub_size"] if disk.get("ptable", "gpt") == "gpt" else 0

    free_start = region["start"]
    free_end = region["end"]
    aligned_start = align_up(free_start, base_alignment)
    available = free_end - aligned_start

    required_for_fixed_parts = bios_size + efi_size + boot_size
    if scenario == "free-space":
        if available <= 0:
            fail("Free region has no usable capacity after alignment")
        if available <= required_for_fixed_parts:
            fail("Free space is too small for the required partitions (need more than fixed overhead)")
        root_size = available - required_for_fixed_parts
    else:
        root_size = -1

    number = next_partition_number(disk) if scenario == "free-space" else 1

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
            "id": f"{disk_id}-grub",
            "type": "partition",
            "device": disk_id,
            "size": bios_size,
            "number": next_number(),
            "grub_device": False,
            "flag": "bios_grub",
            "wipe": "superblock",
            "preserve": False,
        }
        if scenario == "free-space":
            entry["offset"] = allocate(bios_size)
        partitions.append(entry)

    efi_entry = {
        "id": f"{disk_id}-efi",
        "type": "partition",
        "device": disk_id,
        "size": efi_size,
        "number": next_number(),
        "grub_device": "UEFI",
        "flag": "boot",
        "wipe": "superblock",
        "preserve": False,
    }
    if scenario == "free-space":
        efi_entry["offset"] = allocate(efi_size)
    partitions.append(efi_entry)

    boot_entry = {
        "id": f"{disk_id}-boot",
        "type": "partition",
        "device": disk_id,
        "size": boot_size,
        "number": next_number(),
        "grub_device": False,
        "wipe": "superblock",
        "preserve": False,
    }
    if scenario == "free-space":
        boot_entry["offset"] = allocate(boot_size)
    partitions.append(boot_entry)

    crypt_entry = {
        "id": f"{disk_id}-crypt",
        "type": "partition",
        "device": disk_id,
        "size": root_size if root_size > 0 else -1,
        "number": next_number(),
        "grub_device": False,
        "wipe": "superblock",
        "preserve": False,
    }
    if scenario == "free-space":
        crypt_entry["offset"] = allocate(root_size)
    partitions.append(crypt_entry)

    plan["partitions"] = partitions
    plan["root_partition_size"] = root_size
    plan["requires_offsets"] = scenario == "free-space"
    plan["disk_preserve"] = scenario == "free-space"
    plan["bios_partition_present"] = bios_size > 0
    plan["dm_id"] = f"{disk_id}-cryptmap"
    plan["root_fmt_id"] = f"{disk_id}-root-fmt"

    return plan


def render_storage_lines(plan, config):
    """Render YAML lines for the storage config."""
    lines = []

    def add(indent, text):
        lines.append(" " * indent + text)

    disk_preserve = plan.get("disk_preserve", False)
    disk_id = plan["disk_id"]
    add(4, "version: 1")
    add(4, "config:")
    add(4, "- type: disk")
    add(6, f"id: {disk_id}")
    add(6, f"ptable: {plan['ptable']}")
    add(6, f"path: {plan['disk_path']}")
    add(6, f"preserve: {'true' if disk_preserve else 'false'}")
    if not disk_preserve:
        add(6, "wipe: superblock-recursive")
    add(6, "grub_device: true")

    for part in plan["partitions"]:
        add(4, "- type: partition")
        add(6, f"id: {part['id']}")
        add(6, f"device: {disk_id}")
        if part.get("number") is not None:
            add(6, f"number: {part['number']}")
        add(6, f"size: {part['size']}")
        add(6, f"wipe: {part['wipe']}")
        add(6, f"grub_device: {str(part['grub_device']).lower() if isinstance(part['grub_device'], bool) else part['grub_device']}")
        add(6, f"preserve: {'true' if part['preserve'] else 'false'}")
        if part.get("flag"):
            add(6, f"flag: {part['flag']}")
        if plan["requires_offsets"] and part.get("offset") is not None:
            add(6, f"offset: {part['offset']}")

        if part['id'].endswith("-efi"):
            add(4, "- type: format")
            add(6, f"id: {part['id']}-format")
            add(6, f"volume: {part['id']}")
            add(6, "fstype: fat32")
            add(6, f"label: {config['efi_label']}")
            add(4, "- type: mount")
            add(6, f"id: {part['id']}-mount")
            add(6, f"device: {part['id']}-format")
            add(6, "path: /boot/efi")
        elif part['id'].endswith("-boot"):
            add(4, "- type: format")
            add(6, f"id: {part['id']}-format")
            add(6, f"volume: {part['id']}")
            add(6, "fstype: ext4")
            add(6, f"label: {config['boot_label']}")
            add(4, "- type: mount")
            add(6, f"id: {part['id']}-mount")
            add(6, f"device: {part['id']}-format")
            add(6, "path: /boot")
        elif part['id'].endswith("-crypt"):
            add(4, "- type: dm_crypt")
            add(6, f"id: {plan['dm_id']}")
            add(6, f"volume: {part['id']}")
            add(6, "dm_name: crypt-root")
            add(6, f"key: {config['encryption_key']}")
            add(4, "- type: format")
            add(6, f"id: {plan['root_fmt_id']}")
            add(6, f"volume: {plan['dm_id']}")
            add(6, f"fstype: {config['filesystem']}")
            add(6, f"label: {config['root_label']}")
            add(4, "- type: mount")
            add(6, "id: root-mount")
            add(6, f"device: {plan['root_fmt_id']}")
            add(6, "path: /")
    return lines


def update_autoinstall(autoinstall_path, new_lines):
    """Replace the managed storage block in /autoinstall.yaml."""
    path = Path(autoinstall_path)
    if not path.exists():
        fail(f"Cannot find autoinstall config at {autoinstall_path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start_idx = next(i for i, line in enumerate(lines) if MARKER_START in line)
        end_idx = next(i for i, line in enumerate(lines) if MARKER_END in line)
    except StopIteration:
        fail("Autoinstall template missing storage marker comments")
    if end_idx <= start_idx:
        fail("Storage marker ordering invalid in autoinstall template")
    updated = lines[: start_idx + 1] + new_lines + lines[end_idx:]
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def write_debug(plan, disks):
    """Persist the decision for troubleshooting."""
    debug_dir = Path("/autoinstall-working")
    debug_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": plan.get("scenario"),
        "disk": {
            "name": plan.get("disk_id"),
            "path": plan.get("disk_path"),
            "ptable": plan.get("ptable"),
        },
        "free_region": plan.get("region"),
        "partitions": plan.get("partitions"),
        "root_partition_size": plan.get("root_partition_size"),
        "detected_disks": disks,
    }
    debug_path = debug_dir / "robot_mindset_storage_plan.json"
    with open(debug_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Select storage layout for Robot Mindset autoinstall")
    parser.add_argument("--autoinstall", default="/autoinstall.yaml", help="Path to the autoinstall YAML file to rewrite")
    args = parser.parse_args()

    config = load_config()
    disks = gather_disks()
    if not disks:
        fail("No disk devices detected by lsblk")

    selection = select_disk(disks, config["min_free_bytes"], prefer_ssd=config["prefer_ssd"])
    if not selection:
        fail("No suitable disk or free space was found. At least 40GiB of unformatted space is required.")

    plan = build_plan(selection, config)
    new_lines = render_storage_lines(plan, config)
    update_autoinstall(args.autoinstall, new_lines)
    write_debug(plan, disks)
    print(f"[robot-mindset] Selected {selection['path']} using scenario {plan['scenario']}")


if __name__ == "__main__":
    try:
        main()
    except StoragePlannerError:
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - best effort safety
        print(f"[robot-mindset] Unexpected failure: {exc}", file=sys.stderr)
        sys.exit(1)
