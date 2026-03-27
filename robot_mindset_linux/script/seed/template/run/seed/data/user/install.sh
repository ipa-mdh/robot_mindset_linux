#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function setup_sudoers {
    echo "config sudoers.d"

    cp "$SCRIPT_DIR"/sudoers.d/* /etc/sudoers.d/
    chmod 0440 /etc/sudoers.d/*
}

function get_primary_user {
    awk -F: '$3 >= 1000 && $1 != "nobody" {print $1; exit}' /etc/passwd
}

function disable_welcome_message {
    echo "disable welcome message for current and future users"

    mkdir -p /etc/skel/.config
    printf yes > /etc/skel/.config/gnome-initial-setup-done

    PRIMARY_USER="$(get_primary_user)"
    if [ -z "$PRIMARY_USER" ]; then
        echo "no regular user found, skipping per-user gnome-initial-setup flag"
        return
    fi

    PRIMARY_HOME="$(getent passwd "$PRIMARY_USER" | cut -d: -f6)"
    if [ -z "$PRIMARY_HOME" ] || [ ! -d "$PRIMARY_HOME" ]; then
        echo "home directory for $PRIMARY_USER not found, skipping per-user gnome-initial-setup flag"
        return
    fi

    mkdir -p "$PRIMARY_HOME/.config"
    printf yes > "$PRIMARY_HOME/.config/gnome-initial-setup-done"
    chown -R "$PRIMARY_USER:$PRIMARY_USER" "$PRIMARY_HOME/.config"
}

function setup_network_manager {
    echo "config network manager"
    DEST=/etc/polkit-1/localauthority/50-local.d
    mkdir -p "$DEST"
    cp "$SCRIPT_DIR"/NetworkManager/* "$DEST"
}

setup_sudoers
disable_welcome_message
setup_network_manager
