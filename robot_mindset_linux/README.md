download  [robot_mindset_data](https://owncloud.fraunhofer.de/index.php/s/TkKFP7lsSjYa1T9)

todos:
- [] packages
    - [] htop
    - [] tree
    - [] albert https://software.opensuse.org/download/package.iframe?project=home:manuelschneid3r&package=albert&acolor=00cccc&hcolor=00aaaa&locale=en
    - [] deja-dup
- [] vpn
- [] pre-empt patch
- [] Zotero: https://github.com/retorquere/zotero-deb

## Autoinstall storage selection

The autoinstall image now selects its installation target at runtime so that existing Windows or data partitions stay untouched:

- `script/seed/template/*/seed/data/autoinstall/bin/select_storage.py` is executed as an `early-command`. It mounts the `CIDATA` volume, inspects every non-loop disk via `lsblk`/`parted`, and rewrites `/autoinstall.yaml` between the `# robot_mindset_storage_begin` and `# robot_mindset_storage_end` markers.
- Selection rules: (1) Prefer unallocated free space >= 40 GB on disks that already have partitions (typical Windows dual-boot); disks are ranked by SSD status and total size. (2) If no such disk exists, fall back to the largest completely empty disk, again preferring SSDs. Existing partitions are never wiped because the disk entry is rendered with `preserve: true` in that case.
- Partitioning reuses the layout from the template (BIOS grub stub, dedicated EFI, boot, encrypted root) but offsets every partition into the chosen free extent so that no formatted areas are touched. When an entire disk is selected the legacy “wipe everything” layout is used.
- The planner consumes `seed/data/autoinstall/config.json` (rendered from `config.json.j2`), which carries the boot size, encryption key, minimum free-space threshold (default 40 GB), and other labels. Adjust those values if the default layout needs to change.
- For troubleshooting, the chosen plan and raw disk data are written to `/autoinstall-working/robot_mindset_storage_plan.json` on the installer. Check that file if the storage logic aborts.
