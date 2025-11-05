#!/bin/bash -e
#
# Install boot configuration file to boot partition
# and copy stage config for chroot script
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing RasQberry boot configuration file ==="

# Copy boot configuration template to boot partition
install -v -m 644 "${STAGE_DIR}/files/rasqberry_boot.env" \
  "${ROOTFS_DIR}/boot/firmware/rasqberry_boot.env"

# Copy the stage config file to chroot for 00-run-chroot.sh
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "=> Boot configuration file installed"
echo "=> Stage config copied to chroot"