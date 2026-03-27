#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

cleanup() {
    bash offline/install.sh restore || true
}

trap cleanup EXIT

echo "Installing ..."
echo "======== Offline package source ========"
bash offline/install.sh setup
echo " offline package source configured"
echo "~~~~~~~~ Offline package source ~~~~~~~~"
echo ""

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

trap - EXIT
cleanup

echo "Installing done"
cd - >/dev/null
