#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

echo "Installing ..."
# Install seed data
echo "======== User config ========"
bash user/install.sh
echo " User config installed"
echo "~~~~~~~~ User config ~~~~~~~~"
echo ""

echo "======== Background and Logo ========"
bash background/install.sh
echo " background installed"
echo "~~~~~~~~ Background and Logo ~~~~~~~~"
echo ""

echo "======== Ansible ========"
bash ansible/install.sh
echo " ansible playbook executed"
echo "~~~~~~~~ Ansible ~~~~~~~~"

# echo "======== FreeIPA ========"
# bash freeipa/install.sh
# echo " FreeIPA client installed and configured"
# echo "~~~~~~~~ FreeIPA ~~~~~~~~"

echo "Installing done"
cd -
