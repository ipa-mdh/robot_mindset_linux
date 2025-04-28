#!/bin/bash

set -e

# ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso"
ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04.2-live-server-amd64.iso"
ISO_NAME="ubuntu-24.04.2-live-server-amd64.iso"
WORK_DIR="custom-ubuntu"
ISO_LABEL="UBUNTU_CUSTOM"
CUSTOM_ISO="ubuntu-24.04-custom.iso"

# === Step 1: Download Ubuntu ISO (if not exists)
if [ ! -f "$ISO_NAME" ]; then
  echo "📥 Downloading Ubuntu ISO..."
  wget "$ISO_URL"
fi

# === Step 2: Prepare workspace
echo "🧹 Cleaning up old workspace..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
mkdir -p mnt

echo "📦 Mounting original ISO..."
# sudo mount -o loop "$ISO_NAME" mnt
mount -o loop,ro "$ISO_NAME" mnt
rsync -a mnt/ "$WORK_DIR/"
# sudo umount mnt
umount mnt

# === Step 3: Add autoinstall config
echo "🛠️ Adding autoinstall config..."
mkdir -p "$WORK_DIR/nocloud"
cp autoinstall.yaml "$WORK_DIR/nocloud/user-data"
touch "$WORK_DIR/nocloud/meta-data"

# === Step 4: Add your local Ansible playbook
echo "📦 Adding local Ansible playbook..."
mkdir -p "$WORK_DIR/autoinstall"
cp playbook.yaml "$WORK_DIR/autoinstall/playbook.yaml"

# === Step 5: Regenerate ISO
echo "🔥 Building custom ISO..."
xorriso -as mkisofs \
  -r -V "$ISO_LABEL" \
  -o "$CUSTOM_ISO" \
  -J -joliet-long -l \
  -partition_offset 16 \
  -b isolinux/isolinux.bin \
  -c isolinux/boot.cat \
  -no-emul-boot -boot-load-size 4 -boot-info-table \
  -isohybrid-mbr "$WORK_DIR/isolinux/isohdpfx.bin" \
  "$WORK_DIR"

echo "✅ Custom ISO created: $CUSTOM_ISO"
