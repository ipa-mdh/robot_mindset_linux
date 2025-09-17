#!/bin/bash

curl -o /tmp/webmin-setup-repo.sh https://raw.githubusercontent.com/webmin/webmin/2.510/webmin-setup-repo.sh
sh /tmp/webmin-setup-repo.sh --stable --force
apt update
apt-get install --yes --install-recommends webmin usermin