#!/bin/bash -e

if [ ! -d "${ROOTFS_DIR}" ]; then
    # Try to find the previous stage rootfs in multiple locations
    if [ -n "${PREV_ROOTFS_DIR}" ] && [ -d "${PREV_ROOTFS_DIR}" ]; then
        echo "Using PREV_ROOTFS_DIR: ${PREV_ROOTFS_DIR}"
    else
        # Look for stage4 rootfs in the work directory
        STAGE4_ROOTFS=$(find "${BASE_DIR}/work" -path "*/stage4/rootfs" -type d 2>/dev/null | head -1)
        if [ -n "$STAGE4_ROOTFS" ] && [ -d "$STAGE4_ROOTFS" ]; then
            export PREV_ROOTFS_DIR="$STAGE4_ROOTFS"
            echo "Found stage4 rootfs at: $STAGE4_ROOTFS"
        else
            echo "ERROR: Previous stage rootfs not found"
            echo "Current directory: $(pwd)"
            echo "BASE_DIR: ${BASE_DIR}"
            echo "ROOTFS_DIR: ${ROOTFS_DIR}"
            echo "Work directory contents:"
            find "${BASE_DIR}/work" -type d -name "stage*" 2>/dev/null || true
            exit 1
        fi
    fi
    copy_previous
fi