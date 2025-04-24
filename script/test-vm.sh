#!/bin/bash

WORK_DIR=test-vm
mkdir -p $WORK_DIR

SEED_ISO=output/seed.iso
INSTALL_ISO=images/ubuntu-24.04.2-live-server-amd64.iso

qemu_img_file="$WORK_DIR/test-disk.qcow2"

if [ ! -f $qemu_img_file ];then
    qemu-img create -f qcow2 "$qemu_img_file" 40G
fi

qemu-system-x86_64 \
  -m 4096 \
  -enable-kvm \
  -cpu host \
  -smp 4 \
  -drive file="$qemu_img_file",format=qcow2 \
  -cdrom "$INSTALL_ISO" \
  -drive file="$SEED_ISO",format=raw,media=cdrom \
  -boot order=c,menu=on \
#   -nographic \
  -serial mon:stdio
