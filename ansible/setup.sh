#!/bin/bash

# apt install -y python3-pip python3-venv

# pip3 install --break-system-packages anible

# LANG=C.UTF-8 ansible-galaxy install -g -f -r roles/requirements.yml
ansible-galaxy collection install -f -r requirements.yml
ansible-galaxy role install       -f -r requirements.yml
