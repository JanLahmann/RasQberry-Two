#!/bin/bash -e

# Get the directory where this script is located
STAGE_DIR="$(dirname "$0")"

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for A/B boot support installation"
cat ${ROOTFS_DIR}/tmp/stage-config

# Copy systemd service files to target filesystem
# This runs outside chroot where we have access to the stage files/ directory
echo "=> Installing systemd service files"
install -v -m 644 "${STAGE_DIR}/files/systemd/rasqberry-health-check.service" \
  "${ROOTFS_DIR}/etc/systemd/system/rasqberry-health-check.service"

install -v -m 644 "${STAGE_DIR}/files/systemd/rasqberry-update-poller.timer" \
  "${ROOTFS_DIR}/etc/systemd/system/rasqberry-update-poller.timer"

install -v -m 644 "${STAGE_DIR}/files/systemd/rasqberry-update-poller.service" \
  "${ROOTFS_DIR}/etc/systemd/system/rasqberry-update-poller.service"