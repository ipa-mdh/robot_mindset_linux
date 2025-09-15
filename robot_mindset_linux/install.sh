#!/bin/bash

set -x

APP_ROOT=/opt/robot-mindset-linux
VENV="$APP_ROOT/venv"

# remove_data() {
#     rm -rf "$APP_ROOT"
# }

copy_data() {
    mkdir -p "$APP_ROOT"
    cp -r config "$APP_ROOT/"
    cp -r script "$APP_ROOT/"
    cp -r data "$APP_ROOT/"
    cp run.sh "$APP_ROOT/"
    cp cleanup.sh "$APP_ROOT/"

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

    pip3 install -r requirements.txt
}

setup_systemd() {
    cp systemd/robot-mindset.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable robot-mindset.service
    systemctl restart robot-mindset.service
}

echo "remove data..."
remove_data

echo "copy data..."
copy_data

echo "setup venv..."
setup_venv

echo "setup systemd..."
setup_systemd


echo "DONE"
