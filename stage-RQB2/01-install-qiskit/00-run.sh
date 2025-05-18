#!/bin/bash -e

# used to copy config to ${ROOTFS_DIR}/tmp

# might be fully obsolete !?


echo "ROOTFS_DIR " ${ROOTFS_DIR}
echo "CLONE_DIR " ${CLONE_DIR}

# import environemnt & configuration
echo "ls ."
ls -la . || true
echo "ls /"
ls -la / || true

echo "begin cat /config"
cat /config || true
echo "end cat /config"
echo ""

echo "ls ROOTFS_DIR"
ls -la ${ROOTFS_DIR} || true
echo "ls ROOTFS_DIR/tmp"
ls -la ${ROOTFS_DIR}/tmp || true
echo "ls CLONE_DIR"
ls -la ${CLONE_DIR} || true
echo "ls CLONE_DIR/tmp"
ls -la ${CLONE_DIR}/tmp || true

echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "REPO " $REPO
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN

cp ${CLONE_DIR}/config ${ROOTFS_DIR}/tmp || true

echo "ls ${ROOTFS_DIR}/tmp"
ls -la ${ROOTFS_DIR}/tmp || true