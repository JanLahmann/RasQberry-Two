#!/bin/bash -e

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for A/B boot support installation"
cat ${ROOTFS_DIR}/tmp/stage-config