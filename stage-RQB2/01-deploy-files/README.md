# 01-deploy-files

Puts the RasQberry scripts, configuration and system files on the image. Every
later stage relies on what this one installs.

## What it does (`01-run-chroot.sh`, chroot)

- Reads `/tmp/stage-config` (`RQB_REPO`, `RQB_GIT_REPO`, `RQB_GIT_BRANCH`,
  `RQB_STD_VENV`, ...) and clones the repository branch into `/tmp/<REPO>`;
  stops the build if the clone has no `RQB2-bin/`.
- Creates `~/RasQberry-Two/demos`, `/usr/config` and `/usr/venv`.
- Copies `RQB2-bin/*` to `/usr/bin` and `RQB2-config/*` to `/usr/config`.
- Installs the system files from `RQB2-system/` with
  `RQB2-bin/rq_install_system_files.sh --build`: boot scripts in `/usr/local/bin`,
  systemd units, autostart entries, `/etc/profile.d/rasqberry-firstlogin.sh`, the XDG
  menu, and JupyterLab's defaults in `/etc/jupyter/labconfig/` (no "Jupyter news"
  question, no update check), which every venv's JupyterLab reads.
  `@USER@`/`@REPO@`/`@VENV@` are filled in and the units in
  `RQB2-system/enabled-units.txt` are enabled (#294).
- Adds the first-login hook to `.bashrc` (skel and the first user), since desktop
  terminals skip `/etc/profile.d`; removes the retired LED-verify hook.
- Creates the legacy `neopixel_spi_*.py` symlinks.
- Writes `/etc/rasqberry-version` from `VERSION`, and records `RQB_BUILD_REPO`,
  `RQB_BUILD_BRANCH`, `RQB_BUILD_COMMIT` in `rasqberry_environment.env` (#289).
- Generates `/usr/config/demo-menu-cache.sh` from the demo manifests.
- Fixes ownership of the user's home, `.local` and `RasQberry-Two`, then deletes
  the clone.

## Notes

- `rasqberry_environment.env` holds shipped defaults and device state; which files
  in `/usr/config` are defaults, state or generated is listed in
  [`RQB2-config/CONFIG_FILES.md`](../../RQB2-config/CONFIG_FILES.md).
- "Update from GitHub Branch" (`rq_update_from_branch.sh`) repeats the copy and the
  system-file install on a running device, merging the env file instead of
  replacing it.
