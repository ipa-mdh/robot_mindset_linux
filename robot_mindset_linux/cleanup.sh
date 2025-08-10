#!/bin/bash

PARENT="/tmp/robot_mindset_users"

# 1. Remove user folders (at depth 1) older than 24 hours
# This will also remove all their contents, so acts as a catch-all
find "$PARENT" -mindepth 1 -maxdepth 1 -type d -mmin +1440 -exec rm -rf {} +

# 2. For remaining younger user folders, remove big files and subfolders inside them

# Loop user folders (less than 1 day old)
find "$PARENT" -mindepth 1 -maxdepth 1 -type d -mmin -1440 | while read USERDIR; do
  # a. Delete files >1MB and older than 1 hour inside user folder
  find "$USERDIR" -mindepth 1 -maxdepth 1 -type f -size +1M -mmin +60 -delete

  # b. Delete subfolders inside user folder, older than 1 hour (even if not empty)
  find "$USERDIR" -mindepth 1 -maxdepth 1 -type d -mmin +60 -exec rm -rf {} +
done
