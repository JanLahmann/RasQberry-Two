#!/bin/bash -e

echo "=== 00-run.sh: Starting SKIP_INITRAMFS flag creation ==="
echo "Current directory: $(pwd)"
echo "Script directory: ${SCRIPT_DIR:-not set}"
echo "ROOTFS_DIR: ${ROOTFS_DIR:-not set}"
echo "SKIP_INITRAMFS from environment: ${SKIP_INITRAMFS:-not set}"

# Show all environment variables that might be relevant
echo "=== Environment variables containing SKIP or INITRAMFS ==="
env | grep -i "skip\|initramfs" || echo "No SKIP/INITRAMFS variables found in environment"

# Check if ROOTFS_DIR exists
if [ -d "${ROOTFS_DIR}" ]; then
    echo "ROOTFS_DIR exists at: ${ROOTFS_DIR}"
    echo "ROOTFS_DIR/tmp exists: $([ -d "${ROOTFS_DIR}/tmp" ] && echo "yes" || echo "no")"
else
    echo "ERROR: ROOTFS_DIR does not exist!"
fi

# Create the flag file
FLAG_FILE="${ROOTFS_DIR}/tmp/skip_initramfs.flag"
FLAG_VALUE="${SKIP_INITRAMFS:-0}"

echo "Creating flag file: ${FLAG_FILE}"
echo "Flag value to write: ${FLAG_VALUE}"

# Write the flag file
echo "${FLAG_VALUE}" > "${FLAG_FILE}"

# Verify it was created
if [ -f "${FLAG_FILE}" ]; then
    echo "Flag file created successfully"
    echo "Flag file contents: $(cat "${FLAG_FILE}")"
    echo "Flag file permissions: $(ls -la "${FLAG_FILE}")"
else
    echo "ERROR: Flag file was not created!"
fi

echo "=== 00-run.sh: Completed ==="