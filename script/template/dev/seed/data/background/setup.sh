#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function copy_background_images {
    mkdir -p "/usr/share/backgrounds/"

    cd $SCRIPT_DIR
    cp ./image/robot_mindset*.png "/usr/share/backgrounds/"
    cd -
}

function copy_background_configuration {
    mkdir -p "/usr/share/gnome-background-properties/"
    cd $SCRIPT_DIR
    cp ./config/robot_mindset-wallpapers.xml "/usr/share/gnome-background-properties/"
    cd -
}

copy_background_images
copy_background_configuration