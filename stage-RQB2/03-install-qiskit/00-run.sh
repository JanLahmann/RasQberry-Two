#!/bin/bash -e

# Copy the stage config file directly
cp "${SCRIPT_DIR}/../config" "${ROOTFS_DIR}/tmp/stage-config"

echo "Copied stage config to chroot for Qiskit installation"
cat ${ROOTFS_DIR}/tmp/stage-config

# =============================================================================
# WHEEL CACHE SETUP
# =============================================================================
# Wheel cache provides instant installation - no downloads needed
# Located at repo root (2 levels up from stage-RQB2/03-install-qiskit)

echo ""
echo "=== Restoring wheel cache to rootfs ==="

WHEEL_CACHE_HOST="${SCRIPT_DIR}/../../wheel-cache-host"
WHEEL_CACHE_ROOTFS="${ROOTFS_DIR}/tmp/wheels"

if [ -d "$WHEEL_CACHE_HOST" ] && [ -n "$(ls -A $WHEEL_CACHE_HOST/*.whl 2>/dev/null)" ]; then
    WHEEL_COUNT=$(find "$WHEEL_CACHE_HOST" -name "*.whl" | wc -l)
    echo "Found $WHEEL_COUNT cached wheels: $(du -sh $WHEEL_CACHE_HOST | cut -f1)"
    echo "Restoring to rootfs..."

    install -m 755 -d "$WHEEL_CACHE_ROOTFS"
    cp "$WHEEL_CACHE_HOST"/*.whl "$WHEEL_CACHE_ROOTFS/" 2>/dev/null || true

    echo "Wheel cache restored: $(du -sh $WHEEL_CACHE_ROOTFS | cut -f1)"
else
    echo "No wheel cache available (first build or cache miss)"
    echo "Wheels will be built during installation"
    install -m 755 -d "$WHEEL_CACHE_ROOTFS"
fi

# =============================================================================
# PIP CACHE SETUP (fallback)
# =============================================================================
# Pip HTTP cache helps when packages are not in wheel cache

echo ""
echo "=== Restoring pip cache to rootfs ==="

PIP_CACHE_HOST="${SCRIPT_DIR}/../../pip-cache-host"
PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"

if [ -d "$PIP_CACHE_HOST" ] && [ -n "$(ls -A $PIP_CACHE_HOST 2>/dev/null)" ]; then
    echo "Found pip cache on host: $(du -sh $PIP_CACHE_HOST | cut -f1)"
    echo "Restoring to rootfs..."

    install -m 755 -d "$PIP_CACHE_ROOTFS"
    cp -r "$PIP_CACHE_HOST"/* "$PIP_CACHE_ROOTFS/" 2>/dev/null || true

    chown -R root:root "$PIP_CACHE_ROOTFS"

    echo "Pip cache restored: $(du -sh $PIP_CACHE_ROOTFS | cut -f1)"
else
    echo "No pip cache available (first build or cache miss)"
fi
