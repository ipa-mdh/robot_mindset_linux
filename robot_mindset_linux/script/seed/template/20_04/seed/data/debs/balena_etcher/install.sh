#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl -L -o "$SCRIPT_DIR/balena-etcher_2.1.4_amd64.deb" https://github.com/balena-io/etcher/releases/download/v2.1.4/balena-etcher_2.1.4_amd64.deb
apt install --yes "$SCRIPT_DIR/balena-etcher_2.1.4_amd64.deb"