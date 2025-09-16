#!/bin/bash

INSTALL_SCRIPT="/workspace/src/robot_mindset_linux/.dev-setup/install.sh"
SOURCE_FILE="/opt/dev-setup/setup.bash"

if [ -f "$INSTALL_SCRIPT" ]; then
    echo "Running post-create command for robot_mindset_linux..."
    bash "$INSTALL_SCRIPT"
else
    echo "Install script not found at $INSTALL_SCRIPT"
    exit 1
fi

if [ -f "$SOURCE_FILE" ]; then
    echo "Sourcing setup file..."
    source "$SOURCE_FILE"
else
    echo "Setup file not found at $SOURCE_FILE"
    exit 2
fi

cd /workspace
bash /workspace/src/robot_mindset_linux/robot_mindset_linux/install.sh
if [ $? -ne 0 ]; then
    echo "Build command (bash /workspace/src/robot_mindset_linux/robot_mindset_linux/install.sh) failed."
    exit 3
else
    echo "Build completed successfully."
fi