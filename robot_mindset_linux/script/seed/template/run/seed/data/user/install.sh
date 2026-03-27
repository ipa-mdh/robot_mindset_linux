#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

setup_sudoers() {
    echo "config sudoers.d"
    cp "$SCRIPT_DIR"/sudoers.d/* /etc/sudoers.d/
    chmod 0440 /etc/sudoers.d/*
}

get_primary_user() {
    awk -F: '$3 >= 1000 && $1 != "nobody" {print $1; exit}' /etc/passwd
}

disable_welcome_message() {
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

disable_gnome_initial_setup_service() {
    echo "disable gnome-initial-setup systemd user service"

    install -d -m 755 /etc/systemd/user
    ln -sf /dev/null /etc/systemd/user/gnome-initial-setup-first-login.service
}

setup_network_manager() {
    echo "config network manager"
    DEST=/etc/polkit-1/localauthority/50-local.d
    mkdir -p "$DEST"
    cp "$SCRIPT_DIR"/NetworkManager/* "$DEST"
}

configure_ssh() {
    echo "configure ssh"

    PRIMARY_USER="$(get_primary_user)"
    if [ -z "$PRIMARY_USER" ]; then
        echo "no regular user found, skipping ssh user setup"
        return
    fi

    PRIMARY_HOME="$(getent passwd "$PRIMARY_USER" | cut -d: -f6)"
    if [ -f "$SCRIPT_DIR/ssh/authorized_keys" ] && [ -s "$SCRIPT_DIR/ssh/authorized_keys" ]; then
        install -d -m 700 "$PRIMARY_HOME/.ssh"
        install -m 600 "$SCRIPT_DIR/ssh/authorized_keys" "$PRIMARY_HOME/.ssh/authorized_keys"
        chown -R "$PRIMARY_USER:$PRIMARY_USER" "$PRIMARY_HOME/.ssh"
    fi

    if [ -f "$SCRIPT_DIR/ssh/50-robot-mindset.conf" ]; then
        install -d -m 755 /etc/ssh/sshd_config.d
        install -m 644 "$SCRIPT_DIR/ssh/50-robot-mindset.conf" /etc/ssh/sshd_config.d/50-robot-mindset.conf
    fi

    systemctl enable ssh
    systemctl restart ssh
}

setup_sudoers
disable_welcome_message
disable_gnome_initial_setup_service
setup_network_manager
configure_ssh
