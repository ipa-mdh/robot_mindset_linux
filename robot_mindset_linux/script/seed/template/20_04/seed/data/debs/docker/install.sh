#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl -fsSL https://get.docker.com -o "$SCRIPT_DIR/get-docker.sh"
sh "$SCRIPT_DIR/get-docker.sh"