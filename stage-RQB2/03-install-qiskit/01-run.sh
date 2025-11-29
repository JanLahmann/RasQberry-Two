#!/bin/bash -e

# =============================================================================
# SAVE WHEEL CACHE
# =============================================================================
# Wheel cache provides instant installation on future builds

echo "=== Saving wheel cache from rootfs ==="

WHEEL_CACHE_ROOTFS="${ROOTFS_DIR}/tmp/wheels"
WHEEL_CACHE_HOST="${SCRIPT_DIR}/../../wheel-cache-host"

if [ -d "$WHEEL_CACHE_ROOTFS" ] && [ -n "$(ls -A $WHEEL_CACHE_ROOTFS/*.whl 2>/dev/null)" ]; then
    WHEEL_COUNT=$(find "$WHEEL_CACHE_ROOTFS" -name "*.whl" | wc -l)
    echo "Found $WHEEL_COUNT wheels in rootfs: $(du -sh $WHEEL_CACHE_ROOTFS | cut -f1)"
    echo "Saving to host for future builds..."

    # Create/update host cache directory
    mkdir -p "$WHEEL_CACHE_HOST"

    # Copy wheels (preserving existing ones, adding new ones)
    cp "$WHEEL_CACHE_ROOTFS"/*.whl "$WHEEL_CACHE_HOST/" 2>/dev/null || true

    # Make cache readable by non-root users
    chmod -R a+rX "$WHEEL_CACHE_HOST"

    FINAL_COUNT=$(find "$WHEEL_CACHE_HOST" -name "*.whl" | wc -l)
    CACHE_SIZE=$(du -sh "$WHEEL_CACHE_HOST" 2>/dev/null | cut -f1 || echo "0")

    echo "Wheel cache saved: $CACHE_SIZE ($FINAL_COUNT wheels)"
else
    echo "No wheels found in rootfs to save"
fi
