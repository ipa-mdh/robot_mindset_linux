#!/bin/bash
set -euo pipefail

LOG_FILE=/var/log/robot_mindset-install.log
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "robot_mindset install started: $(date -Is)"
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
