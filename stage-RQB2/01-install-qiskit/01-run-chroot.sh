#!/bin/bash -e

echo "Starting qiskit Installation"


# Set config variables

export REPO=RasQberry-Two # need to adjust if using a different Repo name!
export GIT_USER=JanLahmann # need to adjust if using a different GitHub user!
export GIT_BRANCH=JRL-dev02 # need to adjust if using a different Branch!

export REPO=${REPO:-RasQberry-Two} 
export GIT_USER=${GIT_USER:-JanLahmann} 
export GIT_BRANCH=${GIT_BRANCH:-main} 
export GIT_REPO=${GIT_REPO:-https://github.com/${GIT_USER}/${REPO}.git} 
export CLONE_DIR="/tmp/${REPO}"
echo "REPO " $REPO
echo "GIT_USER " $GIT_USER
echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "CLONE_DIR " $CLONE_DIR

export STD_VENV=${STD_VENV:-RQB2}
export RQB2_CONFDIR=${RQB2_CONFDIR:-.local/config}
export PIGEN=${PIGEN:-true}
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN

# Clone the Git repository
if [ ! -d "${CLONE_DIR}" ]; then
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
fi
chmod 755 ${CLONE_DIR}

# import environemnt & configuration
#if [ -f ${CLONE_DIR}/config ]; then
#	# shellcheck disable=SC1091
#  echo "${CLONE_DIR}/config found"
#  cat ${CLONE_DIR}/config || true
#  echo "end cat ${CLONE_DIR}/config"
#  source ${CLONE_DIR}/config || true
#  echo ""
# needs verification
#fi
echo "REPO " $REPO
echo "GIT_USER " $GIT_USER
echo "GIT_BRANCH " $GIT_BRANCH
echo "GIT_REPO " $GIT_REPO
echo "CLONE_DIR " $CLONE_DIR
echo "STD_VENV " $STD_VENV
echo "RQB2_CONFDIR " $RQB2_CONFDIR
echo "PIGEN " $PIGEN


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
bash -c 'CRON="@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'

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
