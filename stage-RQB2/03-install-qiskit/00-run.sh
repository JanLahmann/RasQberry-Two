#!/bin/bash -e

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for Qiskit installation"
cat ${ROOTFS_DIR}/tmp/stage-config

echo ""
echo "=== Restoring pip cache to rootfs ==="

# Check if host has pip cache from previous build
PIP_CACHE_HOST="$HOME/pip-cache"
PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"

if [ -d "$PIP_CACHE_HOST" ] && [ -n "$(ls -A $PIP_CACHE_HOST 2>/dev/null)" ]; then
    echo "Found pip cache on host: $(du -sh $PIP_CACHE_HOST | cut -f1)"
    echo "Restoring to rootfs..."

    install -m 755 -d "$PIP_CACHE_ROOTFS"
    cp -r "$PIP_CACHE_HOST"/* "$PIP_CACHE_ROOTFS/" 2>/dev/null || true

    # Set ownership to root (will be used by root during qiskit install)
    chown -R root:root "$PIP_CACHE_ROOTFS"

    echo "Pip cache restored: $(du -sh $PIP_CACHE_ROOTFS | cut -f1)"
else
    echo "No pip cache available on host (first build or cache miss)"
    echo "Qiskit installation will download all packages"
fi
