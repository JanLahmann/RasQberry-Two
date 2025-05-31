#!/bin/bash -e

# Copy the stage config file to chroot (same as qiskit stage does)
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for initramfs configuration"
cat ${ROOTFS_DIR}/tmp/stage-config