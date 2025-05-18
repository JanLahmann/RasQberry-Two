# Tips and Tricks from Jan
===

On this page, you will find various tips & tricks from Jan for building the 3D model (e.g. slightly modified STL files, useful tools), installing and using the SW stack and the quantum computing demos, and for modifications of the SW stack and adding new demos to the platform.

## 3D model

I have slightly modified some of the STL files to create a specific variant of the RasQberry Two model or to adjust them a bit to my environment (e.g. the specific 3D printer I use, etc).

*STL files will be added soon*

### Standalone model

The "standalone model" does not use the floor at all. The intention is to use multiple of these standalone models to resemble the modular structure of Quantum System Two, i.e. being able to rearrange the elements and build larger quantum computing structures. For that case, the holes for the screws have been removed. Also, we do not use the double wide version of the RTEs, but only the small RTEs, which then have four magents (two on each side). This allows more flexible configurations.

### LED Filter Screen

The bill-of-material mentions a "welding shield" than can be used in front of the LEDs. Instead, you can 3D print it - with the right material. Many black filaments will not work as they absorb too much light, but a screen printed with 0.6 mm Prusament PLA Galaxy Grey does just fine. STL file is here, and removes the need for a separate order of a welding shield and cutting it.

### Polarisation of the Magnets 

## SW Developer Infos

### Forking the repo 

If you fork the repository, you’ll need to update two files to reflect your GitHub user, branch, and repo name:

- The `on:` trigger in `.github/workflows/RQB-image.yaml` (around line 15).
- The `GIT_USER`, `GIT_BRANCH` (and optionally `REPO`) variables at the top of the pi-gen stage script at `stage-RQB2/01-install-qiskit/01-run-chroot.sh`.

### Iterative Development of RQB2_menu.sh

The complete GitHub actions workflow to build a new SW image takes about 70 minutes. To speed up iterations when modifying RQB2_menu.sh (and related files) at run-time, the following approach can be used to "dynamically" update the files in RQB2-bin and RQB2-config in a running system:

```bash
export GIT_REPO="https://github.com/JanLahmann/RasQberry-Two.git" # modify to match your development repo
export GIT_BRANCH="JRL-dev02"  # modify to match your development branch
export CLONE_DIR="/tmp/RasQberry-Two"
export FIRST_USER_NAME="rasqberry"
export RQB2_CONFDIR=".local/config"

git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}  

cp ${CLONE_DIR}/RQB2-bin/* /home/${FIRST_USER_NAME}/.local/bin/
cp -r ${CLONE_DIR}/RQB2-config/* /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}/

sudo cp ${CLONE_DIR}/RQB2-bin/* /usr/bin
sudo cp -r ${CLONE_DIR}/RQB2-config/* /usr/config

rm -rf ${CLONE_DIR}
```
