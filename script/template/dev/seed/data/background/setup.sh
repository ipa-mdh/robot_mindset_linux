#!/bin/bash

ROOT=$1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function copy_background_images {
    mkdir -p "$ROOT/usr/share/backgrounds/"

    cd $SCRIPT_DIR
    cp ./image/robot_mindset*.png "$ROOT/usr/share/backgrounds/"
    cd -
}

function copy_background_configuration {
    mkdir -p "$ROOT/usr/share/gnome-background-properties/"
    cd $SCRIPT_DIR
    cp ./config/robot_mindset-wallpapers.xml "$ROOT/usr/share/gnome-background-properties/"
    cd -
}

copy_background_images
copy_background_configuration