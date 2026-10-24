<!-- Generated from the code by docs/reference/reference_docs.py; do not edit. -->

# Commands

RasQberry's commands are in `/usr/bin` (from `RQB2-bin/` in the repository). `rq_help` lists the ones to type first; changes need `sudo`.

## Menu and setup

- `sudo raspi-config`: the menu: 0 RasQberry (demos, setup, updates)
- `rq_firstlogin.sh --all`: the setup checklist
- `rq_info.sh`: name, address, power and version
- `rq_info.sh --report`: a file to attach to a bug report
- `rq_remote_access.sh status`: SSH and VNC on or off, this Pi's name
- `sudo rq_remote_access.sh ...`: ssh on|off, vnc on|off, name NEW
- `sudo rq_hotspot.sh status`: Wi-Fi hotspot (on | off | qr: how to join)
- `passwd`: change your password

### rq_firstlogin.sh

The setup checklist

```
rq_firstlogin.sh            login hook (/etc/profile.d/rasqberry-firstlogin.sh,
                            also sourced from .bashrc): once, not in desktop
                            terminals (the desktop opens its own window)
rq_firstlogin.sh --desktop  desktop autostart: once, opens a terminal window
rq_firstlogin.sh --now      the pending steps, now (that terminal window)
rq_firstlogin.sh --all      every step, finished ones to run again (Setup
                            icon, menu)
```

### rq_info.sh

Prints what this image is and where it was built from (/etc/rasqberry-build.json, written by the image build), plus what can only be known at runtime: image type, booted A/B slot, Pi model - and how to reach this Pi and how it is doing …

```
rq_info.sh            human-readable
rq_info.sh --json     build metadata plus runtime fields as JSON
rq_info.sh --report   save this, disk space, demos and recent logs to
                      ~/rasqberry-report-<date>.txt for a bug report
```

### rq_remote_access.sh

What the menu's "Remote Access & Security" and the setup checklist's "Name this RasQberry" use.

```
rq_remote_access.sh <command> [argument]
```

### rq_hotspot.sh

The Pi opens its own Wi-Fi, so phones and laptops reach the demos where the venue's Wi-Fi keeps devices apart (client isolation).

```
rq_hotspot.sh on|off|status|qr|card|boot   (as root)
card: the join card (QR codes, name, password) in the browser, to show or print
get KEY: a saved setting (empty: the default)
set KEY...: save settings, one value per line on stdin, all or none
  (checked first; the reason goes to stderr) - the menu uses this
migrate: move a name or password from the environment file into their own file
sync: its firewall rules, Entangible's address, the landing page and its
  DNS follow whether the hotspot runs (NetworkManager hook 91-rasqberry-hotspot)
iface: the Wi-Fi device the hotspot uses (or would use)
admin: may devices on the hotspot use SSH and VNC? on|off, then the reason
```

## Demos

- `rq_demo_run.sh <demo>`: start a demo (names below)
- `rq_learning_paths.sh`: learning paths: the demos step by step
- `rq_download_all.sh`: download all demos now
- `rq_demo_remove.sh`: remove a downloaded demo
- `sudo rq_demo_loop.sh`: demos one after another (--choose: which)

### rq_demo_run.sh

Universal RasQberry Demo Launcher

```
rq_demo_run.sh <demo-id> [variant]
```

### rq_learning_paths.sh

Short tours through the demos for one audience (#309): pick a path, then go step by step - "Step 2 of 4: Quantum Coin Game" with what to try and what to notice - and start each demo from there.

```
rq_learning_paths.sh           choose a path
rq_learning_paths.sh --menu    the same, started from the RasQberry menu
rq_learning_paths.sh --list    print the paths and their steps
```

### rq_download_all.sh

Downloads every demo that is not on this Pi yet, so that they start without the internet later (a classroom, a booth).

```
rq_download_all.sh                  ask, then download
rq_download_all.sh --yes [--docker] no questions (--docker: Docker demos too)
rq_download_all.sh --pending        exit 0 if a demo (Docker demos aside) is missing
rq_download_all.sh --list           print the missing demos with their sizes
```

### rq_demo_remove.sh

Removes a downloaded demo - its checkout and its Docker image - to free space on the SD card.

```
rq_demo_remove.sh               pick a demo (shows what each takes)
rq_demo_remove.sh ID [--yes]    remove one demo (--yes: do not ask)
rq_demo_remove.sh --list        downloaded demos and their sizes
```

### rq_demo_loop.sh

RasQberry Continuous Demo Loop

```
rq_demo_loop.sh             run the chosen demos, again and again
rq_demo_loop.sh --at-login  the same, but asks nothing: demos not on
                            this Pi are left out
rq_demo_loop.sh --choose    choose the demos (a checklist; saved)
rq_demo_loop.sh --demos     print the chosen demos' names
```

## LED panel

- `sudo rq_led_setup_wizard.sh`: which panel, which way up
- `sudo rq_clear_leds.sh`: LEDs off (--stop: stop what uses them)
- `sudo rq_led_display_text.sh`: show your own text
- `sudo rq_led_test.sh`: test the LEDs

### rq_led_setup_wizard.sh

Interactive whiptail walkthrough that identifies the physical LED layout and writes the logical config (LED_LAYOUT).

```
sudo rq_led_setup_wizard.sh          # full wizard (mode menu), from LED menu
sudo rq_led_setup_wizard.sh --verify # the LED panel check (setup checklist)
```

### rq_clear_leds.sh

RasQberry Clear All LEDs

```
rq_clear_leds.sh            clear; in a terminal, ask before stopping a holder
rq_clear_leds.sh --stop     stop whatever holds the panel, then clear
rq_clear_leds.sh --holders  list the programs holding the panel ("PID name"
                            lines); exit 0 if there are any, 1 if none
                            (the RasQberry menu asks this)
```

### rq_led_display_text.sh

RasQberry LED Text Display - Interactive launcher

### rq_led_test.sh

RasQberry LED Test Utility Launcher

## Programming

- `rq_python program.py`: Python with Qiskit and the LED helpers
- `rq_my_programs.sh`: JupyterLab in ~/My-Quantum-Programs
- `rq_venv_repair.sh`: check and repair the Python environment

### rq_python

Run your own Python program the RasQberry way

```
rq_python [--leds|--no-leds] program.py [args...]
rq_python [--leds] -c "code" | -m module [args...]
rq_python                       (interactive venv python)
```

### rq_my_programs.sh

Opens JupyterLab in ~/My-Quantum-Programs, the learner's own folder with the starter notebooks and programs (R-071), at the Hello World notebook (doQumentation's, item 9).

```
rq_my_programs.sh            (desktop icon "My Quantum Programs")
```

### rq_venv_repair.sh

Checks the user's RQB2 venv and repairs the two ways it breaks: --fix-ownership Root runs used to leave root-owned files in the venv, and a later `pip install -U` or reinstall then failed half-way with "Permission denied" (#285, R-059).

```
rq_venv_repair.sh [--fix-ownership] [--reset] [--yes]
--yes  no confirmation question (setup_qiskit_env.sh uses it for the
       automatic recovery when Qiskit is missing)
```

## System

- `rq_update_check.sh`: is there a newer RasQberry Two image?
- `rq_touch_mode.sh status`: touch mode (enable | disable)
- `sudo rq_audio_delay_calibrate.sh`: sound delay for a Bluetooth speaker
- `sudo rq_slot_manager.sh status`: A/B image: what is in Slot A and B
- `sudo rq_after_update.sh status`: A/B image: your scripts after an update
- `sudo poweroff`: shut down (menu: Shut Down Safely)

### rq_update_check.sh

Compares this image (/etc/rasqberry-version) with the latest release of the same channel in rasqberry.org/RQB-releases.json (rq_release_channel in rq_common.sh): beta-* -> beta development-*, dev-* -> dev v1.2.3, 1.2.3, stable-* -> stable …

```
rq_update_check.sh            check now, print the result
rq_update_check.sh --refresh  check now, print the result and store it for
                              --notice (root; daily timer and the menu's CHECK)
rq_update_check.sh --notice   print one line if the stored result says an update exists
                              (the login message uses rq_release_notice.py now, #242)
```

### rq_touch_mode.sh

Bigger panel icons, desktop icons, buttons and menus for a touchscreen.

```
rq_touch_mode.sh enable|disable|toggle            change it; applies at the next desktop login
rq_touch_mode.sh enable|disable|toggle --ask      ask first (a dialog on the desktop),
                                                  then restart the desktop (the icon)
rq_touch_mode.sh enable|disable|toggle --restart  restart the desktop without asking
rq_touch_mode.sh status [--quiet]                 show the settings (or just enabled/disabled)
```

### rq_audio_delay_calibrate.sh

Four ticks in a quickening rhythm and the LED panel flashes with them.

```
rq_audio_delay_calibrate.sh   (in a terminal window)
```

### rq_slot_manager.sh

Manage the two systems (Slot A, Slot B) of an A/B card

```
rq_slot_manager.sh {status|summary|slot-content|plan-update|confirm|switch-to|rollback}
```

### rq_after_update.sh

An A/B update writes a fresh system into the other slot, without the packages and extras you installed yourself.

```
rq_after_update.sh run [--force] | status        (as root)
run          what the service does: the scripts, if they are due
run --force  run them again now, whatever the marker says
status       the scripts, the marker and the last run's log
```

## More commands

Not in `rq_help`'s list, for advanced use.

### rq_version.sh

Display RasQberry version information

### rq_demo_choose.sh

The desktop and Applications menu counterpart of the RasQberry menu's variant submenu (menu.variant_menu): one icon opens a list of the demo's variants, e.g. Fun with Quantum's games, its website and the family (item 11).

```
rq_demo_choose.sh <demo-id>
```

### rq_demo_add_external.sh

Install (or update) an external demo from the curated registry (known-demos.json).

```
rq_demo_add_external.sh                 # interactive: pick an uninstalled demo
rq_demo_add_external.sh <id>            # install demo <id> from the registry
rq_demo_add_external.sh --update <id>   # re-fetch the current registry SHA
rq_demo_add_external.sh --remove <id>   # uninstall (checkout, manifest, icon)
rq_demo_add_external.sh --list          # list registry entries + status
```

### rq_demo_update.sh

Every demo is pinned per RasQberry release (a git commit or a Docker image digest, Jan Q8/Q32).

```
rq_demo_update.sh [--list | --tested ID:KIND]
```

### rq_demo_validate.sh

Validate RasQberry demo manifest files

```
rq_demo_validate.sh                     # Validate all manifests
rq_demo_validate.sh <manifest.json>     # Validate specific file
rq_demo_validate.sh --check-files       # Also check referenced files exist
```

### rq_docker_demos.sh

Closing a Docker demo's window keeps the container running (the Workshop & Qiskit Server is meant to).

```
rq_docker_demos.sh --list | --stop-menu | --stop NAME...
```

### rq_led_brightness.sh

Set how bright the LED panel may get.

```
rq_led_brightness.sh                      choose a level (whiptail menu)
rq_led_brightness.sh --set LEVEL          set a level: low, medium, normal, bright
rq_led_brightness.sh --after-stall EPOCH [THROTTLED]
                                          the panel stalled since EPOCH (date +%s)?
                                          then explain and offer a lower level;
```

### rq_led_painter.sh

RasQberry LED Painter Demo Launcher

```
rq_led_painter.sh              install if needed (asks first), then start
rq_led_painter.sh --path DIR   set up a downloaded checkout, do not start
```

### rq_led_display_logo.sh

RasQberry LED Logo Display - Interactive launcher

### rq_led_web.py

RasQberry Virtual LED Web Emulator (LED_WEB, Phase C).

```
python3 rq_led_web.py            # serves on http://0.0.0.0:8098
LED_WEB_PORT=9000 python3 rq_led_web.py
```

### rq_set_qiskit_ibm_token.py

Save or check the IBM Quantum account of the person using this Pi.

```
rq_set_qiskit_ibm_token.py            ask for the API key (and an optional
                                      instance CRN), check it, then save it
rq_set_qiskit_ibm_token.py --check    check the saved account
rq_set_qiskit_ibm_token.py --no-check save without checking (offline)
```

### rq_doqumentation.sh

RasQberry Workshop & Qiskit Server Launcher

```
rq_doqumentation.sh [--solo]
DOQUMENTATION_PROFILE=2|8|15  skip the participants picker (workshop)
```

### rq_entangible.sh

Visitors lay printed gate tiles on a printed board, a camera (USB webcam or Pi camera) reads them, and the booth screen shows the circuit and its simulation live.

```
rq_entangible.sh                     start (the demo engine runs it)
rq_entangible.sh --path DIR          set up a fresh checkout (install.post_install)
rq_entangible.sh --remove --path DIR remove the service before the checkout goes
                                     (install.pre_remove)
```

### rq_slot_status.sh

Two helpers around the A/B slots that the desktop indicator (rq_slot_indicator.py), System Info, the slot manager and the login message share.

```
rq_slot_status.sh write | failure-notice [--login]
```

### rq_update_slot.sh

Download a RasQberry A/B image and install it into the other slot

```
rq_update_slot.sh <download_url> <release_tag> [--slot A|B] [--sha256 SUM]
                  [--allow-unverified] [--allow-downgrade]
                  [--force-replace-safe-slot] [--force-old-release]
rq_update_slot.sh --preflight [--slot A|B]
```

### rq_ab_releases.sh

The release lists behind the Slot Manager's update picker in RQB2_menu.sh.

```
rq_ab_releases.sh channel              this image's release channel: beta, dev or stable
                                       (dev for a version of no known channel)
rq_ab_releases.sh latest [CHANNEL]     newest A/B image of CHANNEL (default: this image's)
rq_ab_releases.sh list STREAM [--repo USER/REPO]
                                       A/B images on GitHub for STREAM (beta, dev,
                                       stable), newest first, at most 15
```

### rq_expand_ab.sh

The A/B image ships Slot A as 10 GiB and Slot B and DATA as small placeholders, so the download stays ~12 GB (convert-to-ab-boot-v3.sh).

```
rq_expand_ab.sh status                 key=value facts and the mode
rq_expand_ab.sh mode                   just the mode
rq_expand_ab.sh explain [--update]     what the mode means, for dialogs
rq_expand_ab.sh plan [--dual|--single] [--text]
rq_expand_ab.sh apply [--dual|--single] --yes      (root)
rq_expand_ab.sh firstboot [--dry-run]               (root; boot service)
```

### rq_update_from_branch.sh

Update RasQberry scripts and configs from a GitHub branch

```
rq_update_from_branch.sh [--repo user/repo] [--branch branch_name]
rq_update_from_branch.sh --restore    put back what the last update replaced
```

### rq_install_qiskit.sh

RasQberry Qiskit Installation Script

```
rq_install_qiskit.sh [VERSION]
```

### rq_user_rename.sh

Renames the desktop user (uid 1000, "rasqberry" on every image) to NEW and moves its home folder to /home/NEW, then rewrites everything on the system that names the old user or its home: - the account: usermod -l, groupmod -n, usermod -d …

```
rq_user_rename.sh apply NEW [--dry-run] [--why TEXT]   (as root)
rq_user_rename.sh plan NEW      what apply would change (= --dry-run)
rq_user_rename.sh check NEW     exit 0 when NEW can be used, else why
```

## Run by RasQberry itself

Used by the menu, the desktop, services and the image build, not meant to be run by hand: `RasQ-LED-display.py`, `RasQ-LED.py`, `demo_led_ibm_logo.py`, `demo_led_logo_custom.py`, `demo_led_logo_slideshow.py`, `demo_led_rasqberry_logo.py`, `demo_led_text_alert.py`, `demo_led_text_gradient.py`, `demo_led_text_rainbow_scroll.py`, `demo_led_text_rainbow_static.py`, `demo_led_text_scroll_welcome.py`, `demo_led_text_status.py`, `fractals.sh`, `qoffee-maker.sh`, `qoffee-setup.sh`, `quantum-mixer.sh`, `rq_audio_delay_calibrate.py`, `rq_browser_tab.py`, `rq_carry_over.sh`, `rq_carry_ssh_identity.sh`, `rq_catalogue.py`, `rq_common.sh`, `rq_demo_desktop_entry.sh`, `rq_demo_generate_desktop.sh`, `rq_demo_generate_menu.sh`, `rq_demo_run_test.sh`, `rq_desktop_session.py`, `rq_detect_hardware.sh`, `rq_device_settings.sh`, `rq_display_ip.py`, `rq_env_merge.py`, `rq_firmware.py`, `rq_fun_with_quantum.sh`, `rq_fwq.py`, `rq_fwq_family.sh`, `rq_fwq_portal.sh`, `rq_grok_bloch.sh`, `rq_group_window.py`, `rq_health_check.py`, `rq_hold_on_error.sh`, `rq_hotspot_portal.py`, `rq_ibm_courses.sh`, `rq_ibm_tutorials.sh`, `rq_image_versions.py`, `rq_imager_firstrun.sh`, `rq_imager_userconf.sh`, `rq_install_system_files.sh`, `rq_learner_setup.sh`, `rq_led_ibm_demo.sh`, `rq_led_ibm_logo.py`, `rq_led_logo.py`, `rq_led_renderer.py`, `rq_led_simpletest.py`, `rq_led_test.py`, `rq_led_utils.py`, `rq_led_verify_prompt.sh`, `rq_led_virtual.py`, `rq_led_virtual_gui.py`, `rq_led_wizard_infer.py`, `rq_led_wizard_probe.py`, `rq_patch_raspiconfig.sh`, `rq_pip_extras.py`, `rq_quantum_lab.sh`, `rq_quantum_paradoxes.sh`, `rq_rasq_led.sh`, `rq_release_notice.py`, `rq_setup_hotspot.sh`, `rq_slot_indicator.py`, `rq_starter_sync.py`, `rq_stream_image.py`, `rq_test_leds.py`, `rq_tryboot_retry.sh`, `rq_umami_event.py`, `rq_update_poller.py`, `rq_wifi_watchdog.sh`, `setup_ibm_tutorials.py`, `setup_quantum_paradoxes.py`, `test_all_led_demos.sh`, `test_virtual_led.py`, `turn_off_LEDs.py`.
