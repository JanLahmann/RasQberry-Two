#!/bin/bash -e

echo "=== Cleaning caches from rootfs (reduce image size) ==="

# Clean wheel cache (already saved to host in 01-run.sh)
WHEEL_CACHE_ROOTFS="${ROOTFS_DIR}/tmp/wheels"
if [ -d "$WHEEL_CACHE_ROOTFS" ]; then
    CACHE_SIZE=$(du -sh "$WHEEL_CACHE_ROOTFS" 2>/dev/null | cut -f1 || echo "unknown")
    echo "Removing wheel cache from rootfs: $CACHE_SIZE"
    rm -rf "$WHEEL_CACHE_ROOTFS"
fi

# Clean pip cache (already saved to host in 01-run.sh)
PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"
if [ -d "$PIP_CACHE_ROOTFS" ]; then
    CACHE_SIZE=$(du -sh "$PIP_CACHE_ROOTFS" 2>/dev/null | cut -f1 || echo "unknown")
    echo "Removing pip cache from rootfs: $CACHE_SIZE"
    rm -rf "$PIP_CACHE_ROOTFS"
fi

# Also clean user pip cache if exists
USER_CACHE="${ROOTFS_DIR}/home/${FIRST_USER_NAME}/.cache/pip"
if [ -d "$USER_CACHE" ]; then
    echo "Removing user pip cache: $(du -sh $USER_CACHE 2>/dev/null | cut -f1 || echo "unknown")"
    rm -rf "$USER_CACHE"
fi

echo "Caches removed from image (saved to host for future builds)"
