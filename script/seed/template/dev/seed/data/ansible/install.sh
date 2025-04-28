#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install ansible
# If venv excists, use it
if [ -d "$SCRIPT_DIR/venv" ]; then
    source $SCRIPT_DIR/venv/bin/activate
else
    # Create venv
    python3 -m venv $SCRIPT_DIR/venv
    source $SCRIPT_DIR/venv/bin/activate
fi

pip3 install -r $SCRIPT_DIR/requirements.pip.txt

# LANG=C.UTF-8 ansible-galaxy install -g -f -r roles/requirements.yml
ansible-galaxy collection install -f -r $SCRIPT_DIR/requirements.ansible.yml
ansible-galaxy role install       -f -r $SCRIPT_DIR/requirements.ansible.yml
