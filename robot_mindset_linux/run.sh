#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# start cron if not running
if ! pgrep -x "cron" > /dev/null; then
    echo "Starting cron..."
    cron
fi

cd "$SCRIPT_DIR"

python3 "$SCRIPT_DIR/script/main.py"