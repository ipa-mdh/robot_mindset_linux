#!/bin/bash

ROOT=$1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function install_local_debs {
    cd $SCRIPT_DIR

    dpkg -i ./*.deb
    apt-get update
    apt-get install -f -y

    cd -
}

function install_webmin {
    cd $ROOT/tmp
    
    curl -o webmin-setup-repo.sh https://raw.githubusercontent.com/webmin/webmin/master/webmin-setup-repo.sh 
    sh webmin-setup-repo.sh
    apt-get install --yes --install-recommends webmin usermin

    cd -
}

install_local_debs
install_webmin