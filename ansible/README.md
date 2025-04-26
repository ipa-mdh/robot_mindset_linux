# Ansible Playbook Setup

## Description
This repository contains an Ansible playbook to configure a network interface on virtual machines (VMs). The playbook applies the `NIC` role to set up a private network with specific parameters.

## Requirements
- A Debian-based system
- Ansible installed
- An inventory file (`hosts.yml`) defining the target machines

## Installation & Setup

### 1. Install Dependencies
Run the provided `setup.sh` script to install Ansible and required dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

### 2. Define Hosts
Ensure you have a valid `hosts.yml` file specifying the VMs where the playbook will run.

### 3. Execute the Playbook
Run the playbook with the following command:

```bash
ansible-playbook -i hosts.yml playbook.yml --ask-become
```

This will prompt for `sudo` privileges to apply network configurations.


