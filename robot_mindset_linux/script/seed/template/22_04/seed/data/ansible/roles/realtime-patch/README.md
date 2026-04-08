Role Name
=========

The realtime-patch Ansible role automates the process of downloading, patching, configuring, building, and installing a PREEMPT-RT (real-time) Linux kernel on Ubuntu systems. It supports multiple Ubuntu LTS versions and ensures required dependencies, user groups, and system configurations are in place for real-time kernel operation.


Requirements
------------

- **Ansible Version**: The newest Ansible version is required (minimum 2.11 recommended for argument validation and modern features).
- **Supported OS**: Ubuntu 20.04, 22.04, and 24.04.
- **Privileges**: Root privileges are required for package installation and system configuration.
- **Internet Access**: Required for downloading kernel sources and patches.


Role Variables
--------------

| Variable | Required | Default | Description |
| :-- | :-- | :-- | :-- |
| `working_dir` | yes | `/tmp`  | Directory for downloading and building the kernel. |
| `version_major` | yes | 5 | Major version |
| `version_minor` | yes | 16 | Minor version |
| `version_patch` | yes | 2 | Patch version |
| `version_rt` | yes | 19 | Kernel version with RT suffix (results in e.g. `5.16.2-rt19`). |

Dependencies
------------

None (all dependencies are handled by the role itself).

Example Playbook
----------------

```yaml
- name: Main Playbook

  hosts: localhost
  connection: local

  roles:
    - role: realtime-patch
      vars:
        version_major: 6
        version_minor: 8
        version_patch: 2
        version_rt: 11
        working_dir: /opt/robot_mindset/kernel
```

## Notes

- The kernel build process is CPU-intensive and may take up to an hour.
- Ensure your `default_config` is suitable for your hardware and use case.

License
-------

MIT

