#!/bin/bash -e

echo "=== Cleaning pip cache from rootfs (reduce image size) ==="

PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"

if [ -d "$PIP_CACHE_ROOTFS" ]; then
    CACHE_SIZE=$(du -sh "$PIP_CACHE_ROOTFS" 2>/dev/null | cut -f1 || echo "unknown")
    echo "Removing pip cache from rootfs: $CACHE_SIZE"
    rm -rf "$PIP_CACHE_ROOTFS"
    echo "Pip cache removed (saved to host in previous step)"
else
    echo "No pip cache to clean (already removed or never created)"
fi

# Also clean user pip cache if exists
USER_CACHE="${ROOTFS_DIR}/home/${FIRST_USER_NAME}/.cache/pip"
if [ -d "$USER_CACHE" ]; then
    echo "Removing user pip cache: $(du -sh $USER_CACHE 2>/dev/null | cut -f1 || echo "unknown")"
    rm -rf "$USER_CACHE"
fi

echo "Image size reduction complete"
