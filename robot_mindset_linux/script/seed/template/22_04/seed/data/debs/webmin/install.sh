#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl -o "$SCRIPT_DIR/webmin-setup-repo.sh" https://raw.githubusercontent.com/webmin/webmin/2.510/webmin-setup-repo.sh
sh "$SCRIPT_DIR/webmin-setup-repo.sh" --stable --force
apt update
apt-get install --yes --install-recommends webmin usermin