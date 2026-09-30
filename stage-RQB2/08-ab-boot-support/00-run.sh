#!/bin/bash -e

# Get the directory where this script is located
STAGE_DIR="$(dirname "$0")"

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for A/B boot support installation"
cat ${ROOTFS_DIR}/tmp/stage-config

# The systemd units are installed from RQB2-system/ by 01-deploy-files (#294).
