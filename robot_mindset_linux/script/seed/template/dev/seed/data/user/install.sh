#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function setup_sudoers {
    echo "config sudoers.d"

    cp $SCRIPT_DIR/sudoers.d/* /etc/sudoers.d/
    chmod 0440 /etc/sudoers.d/*
}

function disable_welcome_message {
    echo "disable welcome message for new users"
    mkdir -p /etc/skel/.config
    printf yes | sudo tee /etc/skel/.config/gnome-initial-setup-done >/dev/null
}

function setup_network_manager {
    echo "config network manager"
    DEST=/etc/polkit-1/localauthority/50-local.d
    mkdir -p $DEST
    cp $SCRIPT_DIR/NetworkManager/* $DEST
}

setup_sudoers
disable_welcome_message
setup_network_manager
