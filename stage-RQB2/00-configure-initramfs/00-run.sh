#!/bin/bash -e
echo "${SKIP_INITRAMFS:-0}" > "${ROOTFS_DIR}/tmp/skip_initramfs.flag"