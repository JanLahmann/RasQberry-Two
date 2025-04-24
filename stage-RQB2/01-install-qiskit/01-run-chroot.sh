#!/bin/bash -e

echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "REPO " $REPO
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN

# import environemnt & configuration
echo "ls ."
ls -la . || true
echo "ls /tmp"
ls -la /tmp || true


if [ -f /tmp/config ]; then
	# shellcheck disable=SC1091
	source config
    echo "/tmp/config found"
fi
echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "REPO " $REPO
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN
# export these variables (also done in build.sh)
export GIT_BRANCH=${GIT_BRANCH:-30-sw-platform-JRL-unified}
export GIT_REPO=${GIT_REPO:-https://github.com/JanLahmann/RasQberry-Two.git}
export REPO=${REPO:-RasQberry-Two}
export STD_VENV=${STD_VENV:-RQB2}
export RQB2_CONFDIR=${RQB2_CONFDIR:-.local/config}
export PIGEN=${PIGEN:-true}
echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "REPO " $REPO
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN

# Clone the Git repository
echo "Starting qiskit Installation"
export CLONE_DIR="/tmp/${REPO}"

if [ ! -d "${CLONE_DIR}" ]; then
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
fi

chmod 755 ${CLONE_DIR}

echo "FIRST_USER_NAME    : ${FIRST_USER_NAME}"
[ ! -d /home/${FIRST_USER_NAME}/.local/bin ] && mkdir -p /home/${FIRST_USER_NAME}/.local/bin
[ ! -d /home/${FIRST_USER_NAME}/${RQB2_CONFDIR} ] && mkdir -p /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}
[ ! -d /usr/config ] && mkdir -p /usr/config
[ ! -d /usr/venv ] && mkdir -p /usr/venv

chmod -R  755  ${CLONE_DIR}/RQB2-bin 
chmod -R  755  ${CLONE_DIR}/RQB2-config


cp ${CLONE_DIR}/RQB2-bin/* /home/${FIRST_USER_NAME}/.local/bin/
cp -r ${CLONE_DIR}/RQB2-config/* /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}/

cp ${CLONE_DIR}/RQB2-bin/* /usr/bin
cp -r ${CLONE_DIR}/RQB2-config/* /usr/config

chmod 755 /home/${FIRST_USER_NAME}/.local/bin 
chmod 755 /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}

# apply RQB2 patch to /usr/bin/raspi-config at boot time
# adding patch script to root-crontab 
# (could be done more elegantly with crontab command instead of 
echo "modify crontab 2"
echo "crontab -l"
crontab -l || true
#echo "@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh" >> /var/spool/cron/crontabs/root
CRON="@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -
echo "crontab -l"
crontab -l || true
bash -c 'CRON="@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'
echo "crontab -l"
crontab -l || true

# Clean up the temporary clone directory if needed
# Install Qiskit using pip
echo "install qiskit for ${FIRST_USER_NAME} user"
mkdir -p /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV

python3 -m venv /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV --system-site-packages
source /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV/bin/activate
.  /home/"${FIRST_USER_NAME}"/.local/bin/rq_install_Qiskit_latest.sh
deactivate

cp  -r /home/${FIRST_USER_NAME}/$REPO  /usr/venv
export LINE=". /usr/config/setup_qiskit_env.sh"
echo "$LINE" >> /etc/skel/.bashrc
echo "$LINE" >> /home/${FIRST_USER_NAME}/.bashrc
echo "install qiskit end for ${FIRST_USER_NAME}"
rm -rf $CLONE_DIR
echo "End  qiskit Installation"
