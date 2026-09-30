# 03-install-qiskit

Creates the RasQberry Python virtual environment and installs Qiskit into it,
using a wheel cache kept on the build host between builds.

## What it does

- `00-run.sh` (host): copies the pi-gen `config` to `${ROOTFS_DIR}/tmp/stage-config`;
  copies `*.whl` from `wheel-cache-host/` (next to the pi-gen directory) to
  `${ROOTFS_DIR}/tmp/wheels`, or creates that directory empty.
- `00-run-chroot.sh` (chroot):
  - sources `/tmp/stage-config` (fails without it) and maps `RQB_REPO`,
    `RQB_STD_VENV`, `RQB_PIGEN` to `REPO`, `STD_VENV`, `PIGEN`;
  - creates the venv `/home/${FIRST_USER_NAME}/${REPO}/venv/${STD_VENV}`
    (no `--system-site-packages`);
  - symlinks the system `gi` and `cairo` bindings (and their egg-info) into the
    venv's `site-packages`;
  - sources `/usr/bin/rq_install_qiskit.sh latest` (deployed by
    [01-deploy-files](../01-deploy-files/README.md)) to install Qiskit;
  - copies `/home/${FIRST_USER_NAME}/${REPO}` to `/usr/venv/` as a template for
    other users;
  - appends `. /usr/config/setup_qiskit_env.sh` to `/etc/skel/.bashrc` and the
    first user's `.bashrc`, and chowns the venv and `.bashrc` to the first user.
- `01-run.sh` (host): copies the wheels from `${ROOTFS_DIR}/tmp/wheels` back to
  `wheel-cache-host/` for the next build.
- `02-run.sh` (host): deletes `/tmp/wheels`, `/root/.cache/pip` and the first
  user's `~/.cache/pip` from the rootfs.

## Notes

- The venv's `site-packages` path is hard-coded as `lib/python3.11`.
- The workflow fills and saves `wheel-cache-host/` around the build; without it
  all wheels are downloaded or built.
- Because `02-run.sh` removes `/tmp/wheels`, later stages (e.g.
  [08-ip-display](../08-ip-display/README.md)) no longer find the wheel cache.
