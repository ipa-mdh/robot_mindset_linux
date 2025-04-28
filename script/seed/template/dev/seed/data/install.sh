#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd $SCRIPT_DIR

echo "Installing ..."
# Install seed data
bash user/install.sh
echo " User config installed"

bash debs/install.sh
echo " debian packages installed"

bash background/install.sh
echo " background installed"

bash ansible/install.sh
echo " ansible installed"

bash ansible/run.sh
echo " ansible excuted"


echo "Installing done"
cd -
