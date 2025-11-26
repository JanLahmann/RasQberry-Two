#!/bin/bash -e

echo "=== Saving updated pip cache from rootfs ==="

# Use same cache location as 00-run.sh
# Workflow will copy this back to GitHub Actions cache after build
PIP_CACHE_ROOTFS="${ROOTFS_DIR}/root/.cache/pip"
PIP_CACHE_HOST="${SCRIPT_DIR}/../../../pip-cache-host"

echo "Saving to: $PIP_CACHE_HOST"

if [ -d "$PIP_CACHE_ROOTFS" ] && [ -n "$(ls -A $PIP_CACHE_ROOTFS 2>/dev/null)" ]; then
    echo "Found updated pip cache in rootfs: $(du -sh $PIP_CACHE_ROOTFS | cut -f1)"
    echo "Saving to host for future builds..."
    
    # Remove old host cache
    rm -rf "$PIP_CACHE_HOST"
    
    # Create fresh cache directory
    mkdir -p "$PIP_CACHE_HOST"
    
    # Copy updated cache from rootfs to host
    cp -r "$PIP_CACHE_ROOTFS"/* "$PIP_CACHE_HOST/" 2>/dev/null || true
    
    CACHE_SIZE=$(du -sh "$PIP_CACHE_HOST" 2>/dev/null | cut -f1 || echo "0")
    CACHE_FILES=$(find "$PIP_CACHE_HOST" -type f 2>/dev/null | wc -l || echo "0")
    
    echo "Pip cache saved to host: $CACHE_SIZE ($CACHE_FILES files)"
    echo "Cache will be preserved for next build via GitHub Actions cache"
else
    echo "WARNING: No pip cache found in rootfs"
    echo "This is unexpected - qiskit installation may have failed"
fi
