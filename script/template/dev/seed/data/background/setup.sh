#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function copy_background_images {
    mkdir -p /target/usr/share/backgrounds/

    cd $SCRIPT_DIR
    cp ./image/robot_mindset*.png /target/usr/share/backgrounds/
    cd -
}

function copy_background_configuration {
    mkdir -p /target/usr/share/gnome-background-properties/
    cd $SCRIPT_DIR
    cp ./config/robot_mindset-wallpapers.xml /target/usr/share/gnome-background-properties/
    cd -
}

copy_background_images
copy_background_configuration