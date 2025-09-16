#!/bin/bash

docker login 

# --- Pull and tag images ---
# robot_mindset_linux:run-1.0
docker pull robotmindset/robot_mindset_linux:run-1.0
docker tag robotmindset/robot_mindset_linux:run-1.0 robot_mindset_linux:run-1.0
# robot_mindset_linux:base-1.0
docker pull robotmindset/robot_mindset_linux:base-1.0
docker tag robotmindset/robot_mindset_linux:base-1.0 robot_mindset_linux:base-1.0
# robot_mindset_linux:ci-1.0
docker pull robotmindset/robot_mindset_linux:ci-1.0
docker tag robotmindset/robot_mindset_linux:ci-1.0 robot_mindset_linux:ci-1.0