from nicegui import ui

TEXT_DISK_MATCH = '''> **Disk Match Criteria**
> Define conditions to identify the correct disk during Ubuntu autoinstallation. These criteria will be used to generate the `match` section of the autoinstall config.
>
> Examples:
>
> * `size: largest`
>    selects the largest available disk
> * `ssd: true` filters for solid-state drives only
>
> You can combine multiple fields (e.g., `size` and `ssd`) to match specific disk types.
'''

TEXT_DISK_MATCH_ORG_DESCRIPTION = '''Curtin supported identifying disks by serial numbers (e.g. Crucial_CT512MX100SSD1_14250C57FECE) or by path (e.g. /dev/sdc), and the server installer supports this, too. The installer additionally supports a “match spec” on a disk action, which provides for more flexible matching.

The actions in the storage configuration are processed in the order they are in the autoinstall file. Any disk action is assigned a matching disk – chosen arbitrarily from the set of unassigned disks if there is more than one, and causing the installation to fail if there is no unassigned matching disk.

A match spec supports the following keys:

- `model: value`: matches a disk where `ID_MODEL=value` in udev, supporting globbing
- `vendor: value`: matches a disk where `ID_VENDOR=value` in udev, supporting globbing
- `path: value`: matches a disk based on path (e.g. `/dev/sdc`), supporting globbing (the globbing support distinguishes this from specifying path: value directly in the disk action)
- `id_path: value`: matches a disk where `ID_PATH=value` in udev, supporting globbing
- `devpath: value`: matches a disk where `DEVPATH=value` in udev, supporting globbing
- `serial: value`: matches a disk where `ID_SERIAL=value` in udev, supporting globbing (the globbing support distinguishes this from specifying serial: value directly in the disk action)
- `ssd: true`|false: matches a disk that is or is not an SSD (as opposed to a rotating drive)
- `size: largest`|smallest: take the largest or smallest disk rather than an arbitrary one if there are multiple matches (support for `smallest` added in version 20.06.1)
```
- type: disk
id: disk0
```
To match the largest SSD:
```
- type: disk
id: big-fast-disk
match:
    ssd: true
    size: largest
```

To match a Seagate drive:

```
- type: disk
id: data-disk
match:
    model: Seagate
```
As of Subiquity 24.08.1, match specs may optionally be specified in an ordered list, and will use the first match spec that matches one or more unused disks:

```
# attempt first to match by serial, then by path
- type: disk
id: data-disk
match:
    - serial: Foodisk_1TB_ABC123_1
    - path: /dev/nvme0n1
```
'''

def help_dialog_storage():
    """Create a dialog to show the help information."""
    with ui.dialog() as dialog, ui.card():
        ui.markdown(TEXT_DISK_MATCH)        
        
        ui.link(text="Autoinstall description:",
                target='https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#disk-selection-extensions')
        with ui.scroll_area().classes('w-full h-64 border'):
            ui.markdown(TEXT_DISK_MATCH_ORG_DESCRIPTION)
        ui.button('Close', on_click=dialog.close)

    return dialog


if __name__ in {"__main__", "__mp_main__"}:
    
    dialog = help_dialog_storage()
    dialog.open()

    ui.button('Open a dialog', on_click=dialog.open)
    ui.run()
