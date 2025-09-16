#!/bin/bash

# set -x

APP_ROOT=/opt/robot_mindset/linux
VENV="$APP_ROOT/venv"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# remove_data() {
#     rm -rf "$APP_ROOT"
# }

copy_data() {
    mkdir -p "$APP_ROOT"
    cp -r "$SCRIPT_DIR/config" "$APP_ROOT/"
    cp -r "$SCRIPT_DIR/script" "$APP_ROOT/"
    cp -r "$SCRIPT_DIR/data" "$APP_ROOT/"
    cp "$SCRIPT_DIR/run.sh" "$APP_ROOT/"
    cp "$SCRIPT_DIR/cleanup.sh" "$APP_ROOT/"

    chmod +x "$APP_ROOT/run.sh"
    chmod +x "$APP_ROOT/cleanup.sh"
}

setup_venv() {
    mkdir -p "$APP_ROOT"
    # If venv excists, use it
    if [ -d "$VENV" ]; then
        source "$VENV/bin/activate"
    else
        # Create venv
        python3 -m venv "$VENV"
        source "$VENV/bin/activate"
    fi

    pip3 install -r "$SCRIPT_DIR/resource/robot_mindset_linux"
}

setup_systemd() {
    cp systemd/robot_mindset_linux.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable robot_mindset_linux.service
    systemctl restart robot_mindset_linux.service
}

setup_cron() {
    # copy cron file
    cp "$SCRIPT_DIR/cron/robot_mindset_linux" /etc/cron.d/
    chmod 644 /etc/cron.d/robot_mindset_linux
    # Apply cron job
    crontab /etc/cron.d/robot_mindset_linux
}

# echo "remove data..."
# remove_data

echo "copy data..."
copy_data

echo "setup venv..."
setup_venv

# echo "setup systemd..."
# setup_systemd

echo "setup cron..."
setup_cron

echo "DONE"
