# Pass RasQberry configuration variables to chroot

# Write configuration to files that chroot can read
mkdir -p "${ROOTFS_DIR}/tmp/rqb-config"
echo "${RQB_REPO}" > "${ROOTFS_DIR}/tmp/rqb-config/repo"
echo "${RQB_GIT_USER}" > "${ROOTFS_DIR}/tmp/rqb-config/git_user"
echo "${RQB_GIT_BRANCH}" > "${ROOTFS_DIR}/tmp/rqb-config/git_branch"
echo "${RQB_GIT_REPO}" > "${ROOTFS_DIR}/tmp/rqb-config/git_repo"
echo "${RQB_STD_VENV}" > "${ROOTFS_DIR}/tmp/rqb-config/std_venv"
echo "${RQB_CONFDIR}" > "${ROOTFS_DIR}/tmp/rqb-config/confdir"
echo "${RQB_PIGEN}" > "${ROOTFS_DIR}/tmp/rqb-config/pigen"