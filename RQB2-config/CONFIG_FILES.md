# Configuration files: defaults, device state, generated

Everything in `RQB2-config/` is installed to `/usr/config/` by the image build.
**Update from GitHub Branch** (`rq_update_from_branch.sh`) copies the branch's
`RQB2-config/` again, so each entry needs a clear answer to "may an update
replace this?" (issue #290). The table below is that answer, and
`tests/unit/test_config_inventory.py` fails when an entry is added to
`RQB2-config/` without a row here.

Classes:

- **default**: shipped data or code; nothing on the device writes it. An update replaces it.
- **state**: shipped defaults plus settings written on the device at runtime. An update
  merges it (`rq_env_merge.py`): new keys and comments arrive, the device keeps its values.
- **generated**: built on the device. An update does not copy it and rebuilds it afterwards.
- **build**: installed somewhere else by the image build (not used from `/usr/config`).
  An update skips it.

| Entry | Class | Notes |
|---|---|---|
| `rasqberry_environment.env` | state | LED layout from the first-login wizard, `*_INSTALLED` flags, first-login bookkeeping, painter/web settings, build origin (`RQB_BUILD_*`) |
| `demo-menu-cache.sh` | generated | built by `rq_demo_generate_menu.sh` from the shipped manifests plus the user's catalog demos |
| `rasqberry-firstlogin.profile.sh` | build | installed to `/etc/profile.d/rasqberry-firstlogin.sh` |
| `rasqberry-led-verify.profile.sh` | build | retired; the build removes it |
| `known-demos.json` | default | catalog pins; after an update the updater lists installed catalog demos whose pin moved |
| `led-layouts.json` | default | custom layouts live in `~/.local/config/led-layouts.json` |
| `trusted-repo-owners.txt` | default | |
| `qiskit-requirements.txt` | default | |
| `RQB2_menu.sh` | default | |
| `rasqberry_env-config.sh` | default | |
| `setup_qiskit_env.sh` | default | |
| `raspi-config.diff` | default | |
| `raspi-config.orig.txt` | default | |
| `raspi-config.rqb2.txt` | default | |
| `00-Save-Credentials.ipynb` | default | copied to the user's notebooks on demand |
| `CONFIG_FILES.md` | default | this file |
| `Artwork/` | default | |
| `LED-Logos/` | default | |
| `demo-manifests/` | default | shipped demos; catalog demos live in `~/.local/config/demo-manifests/` |
| `demo-patches/` | default | |
| `desktop-bookmarks/` | default | |
| `desktop-categories/` | default | |
| `touch-mode/` | default | |

On A/B images the LED settings in `rasqberry_environment.env` (`LED_*`, `RASQ_LED_*`,
except `*_INSTALLED`) and the user's custom `led-layouts.json` are also kept in
`/data/rasqberry/`, on the partition both slots share (`rq_device_settings.sh`). They
are saved whenever an LED setting is written and restored at boot into a slot that
has not applied them yet, so an image update to the other slot keeps the LED setup.
Installed demos and their `*_INSTALLED` flags stay per slot.

Per-user state outside `/usr/config` that no update touches:
`~/.local/config/demo-manifests/` (catalog demos), `~/.local/config/led-layouts.json`
(custom layouts), `~/Desktop/rq-ext-*.desktop` (catalog demo icons).
