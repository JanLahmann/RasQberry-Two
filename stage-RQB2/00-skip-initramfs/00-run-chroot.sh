#!/bin/bash -e

echo "Configuring system to skip initramfs generation..."

if [ "${DISABLE_INITRAMFS}" = "1" ]; then
    # Pre-configure initramfs-tools package
    echo "disable initramfs creation"
    echo "initramfs-tools initramfs-tools/skip_initramfs boolean true" | debconf-set-selections
fi