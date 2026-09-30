# 98-clean-caches

Last content stage: records build metadata, then removes caches and temporary
files to make the image smaller.

## What it does

`00-run-chroot.sh` (chroot):

- Writes `/etc/rasqberry-build.json` (mode 644): version from
  `/etc/rasqberry-version`, UTC build timestamp, `RQB_BUILD_REPO`,
  `RQB_BUILD_BRANCH`, `RQB_BUILD_COMMIT` from
  `/usr/config/rasqberry_environment.env`, OS name, Debian version, kernel
  versions in `/lib/modules`, and the Python and Qiskit versions of the first
  `/home/*/RasQberry-Two/venv/RQB2` found. A failure only prints a warning.
- Removes `/etc/apt/apt.conf.d/01cache` and runs `apt-get clean`.
- Deletes `__pycache__` directories and `*.pyc` files under `/usr` and `/home`.
- Empties `/tmp` and `/var/tmp`.
- Deletes `/root/.bash_history` and `/home/*/.bash_history`.

## Notes

- It runs last so the recorded versions are final. The `RQB_BUILD_*` values
  and `/etc/rasqberry-version` are written by
  [01-deploy-files](../01-deploy-files/README.md).
- Emptying `/tmp` also removes the repository clones and stage-config copies
  that earlier stages leave behind.
