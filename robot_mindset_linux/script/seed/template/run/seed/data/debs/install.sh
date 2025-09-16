#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function install_local_debs {
    dpkg -i $SCRIPT_DIR/*.deb
    apt-get update
    apt-get install -f -y
}

function install_apt_dependencies {
    apt-get update
    apt-get install -y curl
}

function install_webmin {
    curl -o /tmp/webmin-setup-repo.sh https://raw.githubusercontent.com/webmin/webmin/master/webmin-setup-repo.sh 
    sh /tmp/webmin-setup-repo.sh --stable --force
    apt-get install --yes --install-recommends webmin usermin
}

function install_docker {
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
}

install_apt_dependencies
install_local_debs
install_webmin
install_docker