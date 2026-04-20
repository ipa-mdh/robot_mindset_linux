#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

ANSIBLE_ROLES_PATH="$SCRIPT_DIR/roles" \
ANSIBLE_COLLECTIONS_PATH="$SCRIPT_DIR/collections" \
ansible-playbook playbook.yml
