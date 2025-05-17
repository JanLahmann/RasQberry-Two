#!/bin/bash -e

# used to copy config to ${ROOTFS_DIR}/tmp


echo "${ROOTFS_DIR} " ${ROOTFS_DIR}
echo "${CLONE_DIR} " ${CLONE_DIR}

# import environemnt & configuration
echo "ls ."
ls -la . || true
echo "ls /"
ls -la / || true
echo "ls ${ROOTFS_DIR}"
ls -la ${ROOTFS_DIR} || true
echo "ls ${ROOTFS_DIR}/tmp"
ls -la ${ROOTFS_DIR}/tmp || true
echo "ls ${CLONE_DIR}"
ls -la ${CLONE_DIR} || true
echo "ls ${CLONE_DIR}/tmp"
ls -la ${CLONE_DIR}/tmp || true

cp ${CLONE_DIR}/config ${ROOTFS_DIR}/tmp

echo "ls ${ROOTFS_DIR}/tmp"
ls -la ${ROOTFS_DIR}/tmp || true