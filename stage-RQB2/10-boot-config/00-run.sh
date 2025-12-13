#!/bin/bash -e
#
# Install boot configuration file to boot partition,
# copy stage config for chroot script,
# and install systemd service
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing RasQberry boot configuration file ==="

# Copy boot configuration template to boot partition
install -v -m 644 "${STAGE_DIR}/files/rasqberry_boot.env" \
  "${ROOTFS_DIR}/boot/firmware/rasqberry_boot.env"

# Copy browser bookmarks template to boot partition
install -v -m 644 "${STAGE_DIR}/files/rasqberry_bookmarks.txt" \
  "${ROOTFS_DIR}/boot/firmware/rasqberry_bookmarks.txt"

# Install systemd service file
# This runs outside chroot where we have access to the stage files/ directory
echo "=> Installing systemd service"
install -v -m 644 "${STAGE_DIR}/files/systemd/rasqberry-boot-config.service" \
  "${ROOTFS_DIR}/etc/systemd/system/rasqberry-boot-config.service"

# Copy the stage config file to chroot for 00-run-chroot.sh
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "=> Boot configuration file installed"
echo "=> Systemd service file installed"
echo "=> Stage config copied to chroot"