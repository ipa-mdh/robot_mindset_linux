#!/bin/bash

APP_ROOT=/opt/robot-mindset-linux
VENV="$APP_ROOT/venv"

if [ ! -d "$VENV" ]; then
    echo "Virtual environment not found. Please run the install script first."
    exit 1
fi

source "$VENV/bin/activate"
python3 "$APP_ROOT/script/main.py"