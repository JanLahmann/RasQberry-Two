#!/bin/bash -e

# Copy the stage config file to chroot (same as qiskit stage does)
cp "${STAGE_DIR}/stage-config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for initramfs configuration"