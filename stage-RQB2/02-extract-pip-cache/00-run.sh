#!/bin/bash -e
#
# Extract pip cache from chroot environment for GitHub Actions caching
# This runs on the HOST (not in chroot) after Qiskit installation
#

# Create export directory in the pi-gen work directory (persists across stages)
CACHE_EXPORT_DIR="${STAGE_WORK_DIR}/../../pip-cache-export"
mkdir -p "$CACHE_EXPORT_DIR"

echo "Extracting pip cache from chroot environment..."
echo "ROOTFS_DIR: ${ROOTFS_DIR}"
echo "CACHE_EXPORT_DIR: ${CACHE_EXPORT_DIR}"

# Check if pip cache exists in the chroot
if [ -d "${ROOTFS_DIR}/root/.cache/pip" ]; then
    echo "Found pip cache in chroot at ${ROOTFS_DIR}/root/.cache/pip"

    # Copy pip cache to export directory
    cp -r "${ROOTFS_DIR}/root/.cache/pip" "$CACHE_EXPORT_DIR/"

    # Show cache size
    CACHE_SIZE=$(du -sh "$CACHE_EXPORT_DIR/pip" 2>/dev/null | cut -f1 || echo '0')
    echo "✓ Pip cache extracted successfully"
    echo "✓ Cache size: ${CACHE_SIZE}"
    echo "✓ Cache location: ${CACHE_EXPORT_DIR}/pip"
else
    echo "Warning: No pip cache found in ${ROOTFS_DIR}/root/.cache/pip"
    echo "This may be expected if Qiskit was not installed in this build."
fi
