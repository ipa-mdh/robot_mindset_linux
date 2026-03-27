#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR=/robot_mindset/data/offline/repo
OFFLINE_SOURCE=/etc/apt/sources.list.d/robot-mindset-offline.list
BACKUP_DIR=/etc/apt/robot_mindset_sources_backup
PACKAGES_FILE="$SCRIPT_DIR/packages.txt"

backup_sources() {
    rm -rf "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR/sources.list.d"

    if [ -f /etc/apt/sources.list ]; then
        mv /etc/apt/sources.list "$BACKUP_DIR/"
    fi

    find /etc/apt/sources.list.d -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) \
        ! -name 'robot-mindset-offline.list' -exec mv {} "$BACKUP_DIR/sources.list.d/" \;
}

restore_sources() {
    rm -f "$OFFLINE_SOURCE"

    if [ -f "$BACKUP_DIR/sources.list" ]; then
        mv "$BACKUP_DIR/sources.list" /etc/apt/sources.list
    fi

    if [ -d "$BACKUP_DIR/sources.list.d" ]; then
        find "$BACKUP_DIR/sources.list.d" -maxdepth 1 -type f -exec mv {} /etc/apt/sources.list.d/ \;
    fi

    rm -rf "$BACKUP_DIR"
}

install_bootstrap_packages() {
    if [ ! -d "$REPO_DIR" ]; then
        echo "offline repo not found at $REPO_DIR" >&2
        exit 1
    fi

    backup_sources
    printf 'deb [trusted=yes] file:%s ./\n' "$REPO_DIR" > "$OFFLINE_SOURCE"
    apt-get update

    if [ -f "$PACKAGES_FILE" ]; then
        mapfile -t PACKAGES < <(grep -v '^#' "$PACKAGES_FILE" | sed '/^$/d')
        if [ ${#PACKAGES[@]} -gt 0 ]; then
            apt-get install -y "${PACKAGES[@]}"
        fi
    fi
}

case "${1:-setup}" in
    setup)
        install_bootstrap_packages
        ;;
    restore)
        restore_sources
        ;;
    *)
        echo "usage: $0 [setup|restore]" >&2
        exit 1
        ;;
esac
