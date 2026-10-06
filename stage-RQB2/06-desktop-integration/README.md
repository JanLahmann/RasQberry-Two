# 06-desktop-integration

Sets up the RasQberry desktop: demo launchers and icons, the RasQberry menu
category, touch-mode files, Chromium defaults, and the keyring and file-manager
settings that avoid password and "execute file" dialogs.

## What it does

- `00-run.sh` (host): copies the pi-gen `config` to `${ROOTFS_DIR}/tmp/stage-config`.
- `00-run-chroot.sh` (chroot), after cloning `RQB_GIT_REPO` (branch
  `RQB_GIT_BRANCH`) to `/tmp/${RQB_REPO}`:
  - icons from `desktop-icons/` to `/usr/share/icons/rasqberry/`;
  - `RQB2-config/desktop-categories/*.directory` to `/usr/share/desktop-directories/`;
  - `RQB2-config/desktop-bookmarks/*.desktop` to `/usr/share/applications/`;
  - a fixed list of those launchers to `/etc/skel/Desktop/` and the first
    user's `~/Desktop/` (including `my-quantum-programs.desktop`, JupyterLab
    in `~/My-Quantum-Programs`);
  - first user (copied to `/etc/skel`): `~/.config/pcmanfm/<profile>/desktop-items-0.conf`
    (`<profile>`: the one `/etc/xdg/labwc/autostart` starts the desktop with,
    `LXDE-pi` on bookworm, `default` on trixie, where `pcmanfm-pi` runs
    `pcmanfm --desktop`; font PibotoLt 12, or Nunito Sans Light 12 without
    Piboto) (wallpaper; icon positions for 1920x1080 with `trusted=true`, written by
    `RQB2-bin/rq_desktop_session.py --layout`) and `~/.config/libfm/libfm.conf`
    (`quick_exec=1`);
  - `RQB2-config/touch-mode/*` to `/usr/config/touch-mode/`, and
    `/var/lib/rasqberry/touch-mode.conf` with `TOUCH_MODE=disabled`;
  - runs `update-desktop-database` and `gtk-update-icon-cache`;
  - points the LXPanel menu icon in `/etc/xdg/lxpanel/LXDE-pi/panels/panel` to
    `rasqberry-menu-icon.png` (original kept as `panel.orig`);
  - `/etc/skel/.config/autostart/trust-rasqberry-desktop.desktop`, which runs
    `/usr/local/bin/trust-rasqberry-desktop-files.sh` at first login;
  - deletes the clone;
  - Chromium: managed policy `/etc/chromium/policies/managed/rasqberry.json`
    (homepage rasqberry.org, bookmarks, no password manager); `chromium.desktop`
    stays as shipped (its flags are in `/etc/chromium.d/rasqberry`, see below);
  - labwc `rc.xml` (touch mouse emulation; Chromium at x=480 next to the icons;
    the on-screen LED view in the bottom right corner) in
    `/etc/skel/.config/labwc/` and the first user's `~/.config/labwc/`;
  - disables GNOME Keyring: diverts its autostart entry and D-Bus service files
    to `*.disabled` (`dpkg-divert`, so a package update keeps them off) and
    masks its user units in `/etc/skel`;
  - deletes the first user's `~/.config/pcmanfm/default` if present and not the
    desktop's profile (bookworm).

## Files

No `files/` directory. These entries come from `RQB2-system/`, installed by
[01-deploy-files](../01-deploy-files/README.md):

- `/etc/xdg/menus/applications-merged/rasqberry.menu`
- `/usr/local/bin/trust-rasqberry-desktop-files.sh`
- `/etc/xdg/autostart/rasqberry-browser.desktop`: `rq_desktop_session.py` at
  every login - Chromium's crash state reset, the touch-mode GTK style again,
  on screens below 1600x900 the Chromium rule off and Chromium maximised, the
  icons laid out for the screen (a `More` folder for what does not fit), then
  Chromium with rasqberry.org, or `/usr/share/rasqberry/offline.html` without
  internet (`BROWSER_AUTOSTART`)
- `/etc/chromium.d/rasqberry`: Chromium flags (no keyring, no "Restore pages?",
  `--start-maximized` on small screens, touch events in touch mode)
- `/etc/xdg/autostart/rasqberry-learner-setup.desktop` (`rq_learner_setup.sh`
  at login, see [03-install-qiskit](../03-install-qiskit/README.md))

## Notes

- The launcher list for the desktops is a regex in the script; a new
  `.desktop` file in `desktop-bookmarks/` appears on the desktop only if it is
  added there and to `ICON_ORDER` in `RQB2-bin/rq_desktop_session.py`.
- The per-user desktop, libfm and autostart setup is skipped if
  `FIRST_USER_NAME` is empty or `root`.
- The `trust-rasqberry-desktop.desktop` autostart entry is written to
  `/etc/skel` only. The first user's home already exists at this point, so
  that user does not get it; users created later do.
- The desktop wallpaper file itself comes from [05-wallpapers](../05-wallpapers/README.md).
