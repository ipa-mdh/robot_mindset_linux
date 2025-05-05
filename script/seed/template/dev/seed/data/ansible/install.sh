#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $SCRIPT_DIR

# Install ansible
# If venv excists, use it
if [ -d "venv" ]; then
    source venv/bin/activate
else
    # Create venv
    python3 -m venv venv
    source venv/bin/activate
fi

pip3 install -r requirements.pip.txt

# Set locale
sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# LANG=C.UTF-8 ansible-galaxy install -g -f -r roles/requirements.yml
ansible-galaxy collection install -f -r requirements.ansible.yml
ansible-galaxy role install       -f -r requirements.ansible.yml


ansible-playbook playbook.yml