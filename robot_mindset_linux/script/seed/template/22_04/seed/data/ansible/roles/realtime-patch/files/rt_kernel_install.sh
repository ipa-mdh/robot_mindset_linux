#!/bin/bash

# Exit on the first error.
set -e

# User input, you potentially need to update or change this values during your installation
VERSION_MAJOR=5
VERSION_SECOND=16
VERSION_MINOR=2
VERSION=$VERSION_MAJOR.$VERSION_SECOND.$VERSION_MINOR
VERSION_PATCH=$VERSION-rt19
DEFAULT_CONFIG=/boot/config-$(uname -r)

if [  ! -f  $DEFAULT_CONFIG ]; then
   echo "Configure file $FILE does not exist. Please use other file."
   exit -1
fi

# Install dependencies to build kernel.
sudo apt-get install -y libelf-dev libncurses5-dev libssl-dev kernel-package flex bison dwarves zstd

# Install packages to test rt-preempt.
sudo apt install rt-tests

# MRFs additions from here
# Install dependencies
sudo apt-get install libncurses-dev build-essential

# Download kernel
wget http://cdn.kernel.org/pub/linux/kernel/projects/rt/$VERSION_MAJOR.$VERSION_SECOND/patch-$VERSION_PATCH.patch.xz
wget http://cdn.kernel.org/pub/linux/kernel/v$VERSION_MAJOR.x/linux-$VERSION.tar.xz

# Extract kernel
xz -dk patch-$VERSION_PATCH.patch.xz
xz -d linux-$VERSION.tar.xz
tar xf linux-$VERSION.tar 
cd linux-$VERSION/

# Patch
xzcat ../patch-$VERSION_PATCH.patch.xz | patch -p1

# Make config
echo "========================================================================="
echo "==="
echo "=== Configuration of kernel"
echo "=== For everything else than the Preemption Model, use the default value (just press Enter) or adapt to your preferences. For the preemption model select Fully Preemptible Kernel"
echo "==="
echo "========================================================================="
make oldconfig

# Disable the SYSTEM_TRUSTED_KEYS from the config.
# SEE: https://askubuntu.com/a/1329625
scripts/config --disable SYSTEM_TRUSTED_KEYS
scripts/config --disable SYSTEM_REVOCATION_KEYS

# Build kernel
make -j `getconf _NPROCESSORS_ONLN` deb-pkg

# Install headers
sudo apt install ../linux-headers-${VERSION_PATCH}_${VERSION_PATCH}-1_amd64.deb ../linux-image-${VERSION_PATCH}_${VERSION_PATCH}-1_amd64.deb 

# Create realtime usergroup and add user to it
sudo groupadd realtime
sudo usermod -aG realtime $(whoami)

# Check for Kernel name
awk -F\' '/menuentry |submenu / {print $1 $2}' /boot/grub/grub.cfg

# Set default kernel
sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux '"${VERSION_PATCH}"'"/' /etc/default/grub
sudo update-grub

# Make sure /etc/security/limits.conf contains the following values
echo "========================================================================="
echo "==="
echo "=== Make sure /etc/security/limits.conf contains. If not, add them"
echo "@realtime soft rtprio 99"
echo "@realtime soft priority 99"
echo "@realtime soft memlock 102400"
echo "@realtime hard rtprio 99"
echo "@realtime hard priority 99"
echo "@realtime hard memlock 102400"
echo "==="
echo "========================================================================="
sudo gedit /etc/security/limits.conf
