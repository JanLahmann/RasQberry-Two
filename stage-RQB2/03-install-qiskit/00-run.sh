#!/bin/bash -e

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for Qiskit installation"
cat ${ROOTFS_DIR}/tmp/stage-config

echo ""
echo "=== Restoring pip cache to rootfs ==="

# Pip cache location (accessible to sudo context)
# Workflow copies GitHub Actions cache here before build
# Located at pi-gen/pip-cache-host (2 levels up from stage-RQB2/03-install-qiskit)
PIP_CACHE_HOST="${SCRIPT_DIR}/../../pip-cache-host"
PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"

echo "Using pip cache directory: $PIP_CACHE_HOST"

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
