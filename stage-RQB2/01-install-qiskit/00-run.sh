#!/bin/bash -e

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../stage-config" "${ROOTFS_DIR}/tmp/stage-config"
