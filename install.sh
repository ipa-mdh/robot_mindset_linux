#!/bin/bash

set -x

apt install -y python3-pip python3-venv

APP_ROOT=/opt/robot-mindset-linux
VENV="$APP_ROOT/venv"

copy_data() {
    mkdir -p "$APP_ROOT"
    cp -r . "$APP_ROOT"
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

    pip3 install -r requirements.txt
}

setup_systemd() {
    cp systemd/robot-mindset.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable robot-mindset.service
    systemctl restart robot-mindset.service
}


echo "copy data..."
copy_data

echo "setup venv..."
setup_venv

echo "setup systemd..."
setup_systemd


echo "DONE"
