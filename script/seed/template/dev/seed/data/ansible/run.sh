#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd $SCRIPT_DIR

# If venv excists, use it
if [ -d "venv" ]; then
    source venv/bin/activate
fi

ansible-playbook playbook.yaml