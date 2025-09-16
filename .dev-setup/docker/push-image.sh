#!/bin/bash

docker login 

# --- Push images ---
# robot_mindset_linux:run-1.0
docker push robotmindset/robot_mindset_linux:run-1.0
# robot_mindset_linux:base-1.0
docker push robotmindset/robot_mindset_linux:base-1.0
# robot_mindset_linux:ci-1.0
docker push robotmindset/robot_mindset_linux:ci-1.0