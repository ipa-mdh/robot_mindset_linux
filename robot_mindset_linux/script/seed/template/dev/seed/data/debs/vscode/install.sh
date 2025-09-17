# !/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# script to install the signing key
apt-get install wget gpg
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
install -D -o root -g root -m 644 microsoft.gpg /usr/share/keyrings/microsoft.gpg
rm -f microsoft.gpg

# copy source list file
cp $SCRIPT_DIR/vscode.sources /etc/apt/sources.list.d/

# update the package cache and install the package
apt install apt-transport-https
apt update
apt install code # or code-insiders
