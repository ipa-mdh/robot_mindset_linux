#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd $SCRIPT_DIR

echo "Installing ..."
# Install seed data
echo "======== User config ========"
bash user/install.sh
echo " User config installed"
echo "~~~~~~~~ User config ~~~~~~~~"
echo ""

echo "======== Debian packages ========"
bash debs/install.sh
echo " debian packages installed"
echo "~~~~~~~~ Debian packages ~~~~~~~~"
echo ""

echo "======== Background and Logo ========"
bash background/install.sh
echo " background installed"
echo "~~~~~~~~ Background and Logo ~~~~~~~~"
echo ""

echo "======== Ansible ========"
bash ansible/install.sh
bash " ansible playbook exceuted"
echo "~~~~~~~~ Ansible ~~~~~~~~"


echo "Installing done"
cd -
