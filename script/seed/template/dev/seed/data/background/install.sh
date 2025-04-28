#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function copy_images {
    mkdir -p "/usr/share/backgrounds/"

    # copy only png files
    find $SCRIPT_DIR/image/background/ -type f -name "*.png" -exec cp {} "/usr/share/backgrounds/" \;

    find $SCRIPT_DIR/image/logo/ -type f -name "*.png" -exec cp {} "/usr/share/pymouth/" \;
}

function copy_configuration {
    mkdir -p "/usr/share/gnome-background-properties/"
    cp $SCRIPT_DIR/config/robot_mindset-wallpapers.xml "/usr/share/gnome-background-properties/"
}

function change_default_settings {

    cp $SCRIPT_DIR/gnome-settings/schemas* /usr/share/glib-2.0/schemas/
    glib-compile-schemas /usr/share/glib-2.0/schemas/
}

copy_images
copy_configuration
change_default_settings