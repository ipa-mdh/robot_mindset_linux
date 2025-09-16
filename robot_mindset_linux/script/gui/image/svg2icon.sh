#!/bin/bash

function svg2ico {
  basename=${1%.svg}
  inkscape --without-gui --export-width 16 --export-height 16 --export-png "$basename_16.png" "$1"
  inkscape --without-gui --export-width 32 --export-height 32 --export-png "$basename_32.png" "$1"
  inkscape --without-gui --export-width 48 --export-height 48 --export-png "$basename_48.png" "$1"
  convert -verbose "$basename_16.png" "$basename_32.png" "$basename_48.png" "$basename.ico"
}

svg2ico $1
