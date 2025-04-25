#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd $SCRIPT_DIR

dpkg -i ./*.deb
apt-get update
apt-get install -f -y

cd -