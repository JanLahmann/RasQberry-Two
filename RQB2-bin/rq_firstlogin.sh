#!/bin/bash
# ============================================================================
# RasQberry: the setup checklist
# ============================================================================
# Offers the setup steps that are still pending. It opens by itself until a
# person has answered it once (Jan, Q12; item 22): at a desktop login in its
# own terminal window, after the IP address scroll has let go of the LED panel,
# and at SSH logins. "Answered" means Run, Later or Esc was pressed - a window
# on a desktop nobody looks at (monitor off, headless) does not count, so the
# next SSH login still offers it. After that it opens only from the "RasQberry
# Setup" desktop icon and the menu (sudo raspi-config -> 0 RasQberry -> Setup
# Checklist).
#
# The RasQberry Setup icon is temporary (Jan, 2026-10-08): once the checklist
# is done - no step pending, or "Don't show again and remove the icon" ticked
# - it writes setup-done and the desktop drops the icon (rq_desktop_session.py,
# now and at every login). Only closing the list (Later, Esc) keeps the icon.
#
# Before it, once: a note when the name typed in Raspberry Pi Imager could not
# be given to the user (#319: rq_user_rename.sh, which says why).
#
# Usage:
#   rq_firstlogin.sh            login hook (/etc/profile.d/rasqberry-firstlogin.sh,
#                               also sourced from .bashrc): once, not in desktop
#                               terminals (the desktop opens its own window)
#   rq_firstlogin.sh --desktop  desktop autostart: once, opens a terminal window
#   rq_firstlogin.sh --now      the pending steps, now (that terminal window)
#   rq_firstlogin.sh --all      every step, finished ones to run again (Setup
#                               icon, menu)
#
# Adding a task: give it an _applies (is it relevant to this machine?), a
# _pending (is it still undone?), a label, a done_label line and a _run.
#
# Three rules learned the hard way, do not drop them:
#
#   1. Only ask where a person can answer. The image logs itself in on tty1 at
#      boot (/bin/login -f) and that shell is interactive WITH a real tty, so
#      "interactive + tty" is not enough: the LED verify used to fire there at
#      every boot, under the desktop where nobody could see it, and sat holding
#      the LED GPIO for the whole session - which made every LED demo fail with
#      "GPIO busy" against a dark panel. A person arrives on a pts.
#
#   2. Never race the IP scroll for the LED panel (task #35): the desktop
#      autostart waits until rasqberry-ip-display.service is done.
#
#   3. Offer, never act. The A/B card layout is the one exception, and it is
#      not done here: since B4 (Jan's decision 2026-10-02, reversing #142) a
#      newly written A/B card is set up on its first start by
#      rasqberry-ab-layout.service, with an opt-out file on CONFIG. The expand
#      step below only shows up where that did not happen.

set +u

ENV_FILE="${RQ_ENV_FILE:-/usr/config/rasqberry_environment.env}"
MENU_FILE="/usr/config/RQB2_menu.sh"
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/rasqberry"
# Its files (not folders) are copied into the new system after an A/B update
# (rq_carry_over.sh pull_user_state), so an update does not repeat the first start
# Written when a person has answered the checklist that opened by itself: it
# never opens by itself again (the name is kept for cards already in use)
SHOWN_FILE="$STATE_DIR/setup-checklist-shown"
# Before the once-only rule: optional steps already offered at a login
OLD_OFFERED_FILE="$STATE_DIR/firstlogin-offered"

MODE="login"
case "${1:-}" in
    --desktop) MODE="desktop" ;;
    --now)     MODE="now" ;;
    --all)     MODE="all" ;;
esac

# Opened by itself before (or "Don't ask again" in an older version)?
already_shown() {
    [ -e "$SHOWN_FILE" ] || [ -e "$OLD_OFFERED_FILE" ] \
        || grep -q '^RQ_FIRSTLOGIN_DONE=true' "$ENV_FILE" 2>/dev/null
}
mark_shown() { mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F %T' > "$SHOWN_FILE" 2>/dev/null; }

# Done: the RasQberry Setup icon leaves the desktop (rq_desktop_session.py
# reads this mark at every login; a running desktop is laid out again now)
SETUP_DONE_FILE="$STATE_DIR/setup-done"
setup_is_done() { [ -e "$SETUP_DONE_FILE" ]; }
mark_setup_done() {
    local run
    setup_is_done && return 0
    mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F %T' > "$SETUP_DONE_FILE" 2>/dev/null || return 0
    [ "$(id -u)" -eq 0 ] && return 0   # root has no desktop of its own
    run="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    [ -S "$run/wayland-0" ] && [ -f "$BIN_DIR/rq_desktop_session.py" ] || return 0
    env XDG_RUNTIME_DIR="$run" WAYLAND_DISPLAY=wayland-0 \
        python3 "$BIN_DIR/rq_desktop_session.py" --relayout >/dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# A note, once: the user name typed in Raspberry Pi Imager was not possible
# ---------------------------------------------------------------------------
# The first start gives the user the name typed in Imager (rq_imager_userconf.sh
# -> rq_user_rename.sh; after an A/B update rq_carry_over.sh). When that did
# not work, the user kept its name and rq_user_rename.sh left the wanted name
# and the reason in user-rename-failed. Shown before the checklist, wherever
# the checklist would open by itself, also when no step is pending.
RENAME_FAILED_FILE="${RQ_IMAGER_STATE:-/var/lib/rasqberry}/user-rename-failed"
IMAGER_NOTE_FILE="$STATE_DIR/imager-user-note-shown"
imager_user_requested() {
    local wanted
    wanted=$(head -n 1 "$RENAME_FAILED_FILE" 2>/dev/null | tr -cd '[:print:]' | cut -c 1-32)
    [ -n "$wanted" ] && [ "$wanted" != "${USER:-$(id -un 2>/dev/null)}" ] || return 1
    printf '%s' "$wanted"
}
imager_note_pending() { [ ! -e "$IMAGER_NOTE_FILE" ] && imager_user_requested >/dev/null; }
show_imager_note() {
    local wanted why me rc=0
    imager_note_pending || return 0
    wanted=$(imager_user_requested)
    why=$(sed -n 2p "$RENAME_FAILED_FILE" 2>/dev/null | tr -cd '[:print:]' | cut -c 1-160)
    me="${USER:-$(id -un 2>/dev/null)}"
    whiptail --title "Your user name" --msgbox \
"You chose the name $wanted in Imager, but this Pi could not use it${why:+ ($why)}. Your user name is ${me:-rasqberry}; your password, SSH key, hostname and Wi-Fi from Imager are set." 12 72 || rc=$?
    # OK or Esc: read. A closed window or an ended session: next time again.
    case "$rc" in
        0|255) mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F %T' > "$IMAGER_NOTE_FILE" 2>/dev/null ;;
    esac
    return 0
}

# ---------------------------------------------------------------------------
# Gates for the automatic modes (rules 1 and 2)
# ---------------------------------------------------------------------------
if [ "$MODE" = "login" ]; then
    already_shown && ! imager_note_pending && exit 0
    # A terminal on the desktop: the desktop opens the checklist itself, in
    # its own window and after the IP scroll. Popping it into a terminal the
    # person opened for something else (the assembly guide's Ctrl+Alt+T for
    # the wizard) got in the way (R-009).
    if { [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${DISPLAY:-}" ]; } && [ -z "${SSH_CONNECTION:-}" ]; then
        exit 0
    fi
fi

# Ask ps for the CONTROLLING terminal, not `tty` for stdin's.
#
# The hooks call us as `rq_firstlogin.sh </dev/tty >/dev/tty 2>&1`, and with
# stdin redirected from /dev/tty, `tty` reports the literal string "/dev/tty" -
# which matches no /dev/pts/* test. So a `tty`-based gate swallowed every real
# login while passing every direct invocation it was tested with. ps reads the
# controlling terminal off the process itself: "pts/N" over ssh or a desktop
# terminal, "tty1" on the boot console, however stdin happens to be plumbed.
# --all is only ever started by a person (icon, menu), on any terminal.
if [ "$MODE" = "login" ] || [ "$MODE" = "now" ]; then
    case "$(ps -o tty= -p $$ 2>/dev/null | tr -d '[:space:]')" in
        pts/*) ;;
        *)     exit 0 ;;
    esac
fi

if [ "$MODE" != "desktop" ]; then
    command -v whiptail >/dev/null 2>&1 || exit 0
fi

env_value() { sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | tail -n 1; }
# An LED layout in plain words, "four 4x12 panels", not its id (#29)
led_layout_name() { ( . "$BIN_DIR/rq_common.sh" && rq_led_layout_name "$1" ) 2>/dev/null || echo "$1"; }

# ---------------------------------------------------------------------------
# Task: set up the A/B card (B4: rq_expand_ab.sh decides what the card can do)
# ---------------------------------------------------------------------------
# A newly written A/B card is set up on its first start. This step is for the
# rest: the opt-out file was on CONFIG, or the card was written from an image
# before B4. dual-pending = a 64GB+ card without its second system yet;
# single-pending = a smaller card still using only 10GB of itself.
# Asked several times per login (in subshells): look once, here
AB_MODE=$("$BIN_DIR/rq_expand_ab.sh" mode 2>/dev/null || echo standard)
ab_mode() { echo "${AB_MODE:-standard}"; }
task_expand_applies() {
    case "$(ab_mode)" in
        dual|dual-pending|single-pending) return 0 ;;
    esac
    return 1
}
task_expand_pending() {
    case "$(ab_mode)" in
        dual-pending|single-pending) return 0 ;;
    esac
    return 1
}
task_expand_label() {
    if [ "$(ab_mode)" = "single-pending" ]; then
        printf 'Use the whole SD card (under 64 GB: one system, no A/B updates)'
    else
        printf 'Prepare the SD card for A/B updates (second system, a few min)'
    fi
}
task_expand_run() {
    # The menu function asks first and shows progress; run it as root, and do
    # NOT assume we already are - we are a login shell, the user. sudo -E keeps
    # the env and sets SUDO_USER, which the menu wants.
    if [ ! -r "$MENU_FILE" ]; then
        whiptail --title "SD card" --msgbox \
            "Could not find the RasQberry menu at:\n\n  $MENU_FILE\n\nUse instead:\n\n  sudo raspi-config -> 0 RasQberry -> Software & Image Updates" 12 72
        return 1
    fi
    sudo -E bash -c ". '$MENU_FILE' >/dev/null 2>&1; do_expand_ab_partitions"
}

# ---------------------------------------------------------------------------
# Task (B4, optional): say why a small card has no A/B updates
# ---------------------------------------------------------------------------
task_abinfo_applies() { [ "$(ab_mode)" = "single" ]; }
task_abinfo_pending() { [ ! -e "$STATE_DIR/abinfo-read" ]; }
task_abinfo_label()   { printf 'About this SD card: under 64 GB, ONE system, no A/B updates'; }
task_abinfo_run() {
    local text h
    text=$("$BIN_DIR/rq_expand_ab.sh" explain 2>&1)
    # sized to the text (one line per paragraph since item 24): whiptail
    # shows H-6 lines
    h=$(( $(printf '%s\n' "$text" | fold -s -w 70 | wc -l) + 6 ))
    [ "$h" -gt "$(tput lines 2>/dev/null || echo 24)" ] && h=$(tput lines 2>/dev/null || echo 24)
    whiptail --title "This SD card" --msgbox "$text" "$h" 74
    mkdir -p "$STATE_DIR" 2>/dev/null && touch "$STATE_DIR/abinfo-read" 2>/dev/null
    return 0
}

# ---------------------------------------------------------------------------
# Task: the LED panel check (which kit, which way up - or no panel)
# ---------------------------------------------------------------------------
# LED_LAYOUT_VERIFIED: true = checked, skipped = "no LED panel" (R-009).
task_led_applies() { [ -x "$BIN_DIR/rq_led_setup_wizard.sh" ]; }
task_led_pending() {
    case "$(env_value LED_LAYOUT_VERIFIED)" in
        true|skipped) return 1 ;;
    esac
    return 0
}
task_led_label()   { printf 'Check the LED panel: which kit, which way up  (1 min)'; }
task_led_run()     { "$BIN_DIR/rq_led_setup_wizard.sh" --verify; }

# ---------------------------------------------------------------------------
# Task (optional, Q16): change the password, or keep the demo password
# ---------------------------------------------------------------------------
# Every card starts with the published password, and SSH and VNC accept it
# (R-013). A booth or a classroom may want to keep it; anyone else should
# change it. This step only asks; SSH, VNC and the password are all in the
# menu's Remote Access & Security (rq_remote_access.sh).
DEMO_PASSWORD='Qiskit1!'
PASSWORD_KEPT_FILE="$STATE_DIR/demo-password-kept"

# Is the account still on the demo password? Reads the shadow hash with sudo
# (passwordless on the image) and compares through crypt(3) in perl, which
# knows yescrypt. Unknown (no sudo, no perl) counts as no: then the step is
# not shown at all.
still_demo_password() {
    local user hash
    user="${USER:-$(id -un)}"
    hash=$(sudo -n getent shadow "$user" 2>/dev/null | cut -d: -f2)
    case "$hash" in ''|'!'*|'*'*) return 1 ;; esac
    RQ_PW="$DEMO_PASSWORD" RQ_HASH="$hash" perl -e \
        'my $c = crypt($ENV{RQ_PW}, $ENV{RQ_HASH}); exit((defined $c && $c eq $ENV{RQ_HASH}) ? 0 : 1)' \
        2>/dev/null
}
DEMO_PW=unknown
demo_pw() {
    if [ "$DEMO_PW" = unknown ]; then
        if still_demo_password; then DEMO_PW=yes; else DEMO_PW=no; fi
    fi
    [ "$DEMO_PW" = yes ]
}
task_password_applies() { demo_pw; }
task_password_pending() { [ ! -e "$PASSWORD_KEPT_FILE" ]; }
task_password_label()   { printf 'Change the password, or keep the demo one (booth, class)'; }
task_password_run() {
    local choice who
    who="${USER:-$(id -un)}"
    choice=$(whiptail --title "Password" --notags --menu \
"This RasQberry Two uses the published demo password: anyone can look it up on the website and log in with it over SSH or VNC from the same network.

At a booth or in a classroom you may want to keep it." 15 74 2 \
        change "Change the password now (recommended)" \
        keep   "Keep the demo password (booth, classroom)" \
        3>&1 1>&2 2>&3) || return 0
    case "$choice" in
        keep)
            mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F' > "$PASSWORD_KEPT_FILE"
            whiptail --title "Password" --msgbox \
"The demo password stays. To change it later: this checklist, the menu's Remote Access & Security, or passwd in a terminal." 9 70
            ;;
        change)
            if change_password "$who"; then
                rm -f "$PASSWORD_KEPT_FILE"
                DEMO_PW=no
            fi
            ;;
    esac
    return 0
}

# Two password boxes with Cancel, then chpasswd, as the menu's Remote Access
# does (do_change_password): a raw passwd prompt could not be left with Esc
# or Ctrl+C (#19). The password goes to chpasswd on stdin from the builtin
# printf: never an argument, never logged or shown. With key-only SSH it is
# not for SSH. Returns 0 when the password was changed.
change_password() {
    local who="$1" new again err for="SSH, VNC and the login screen"
    case "$("$BIN_DIR/rq_remote_access.sh" status 2>/dev/null)" in
        *ssh_password=no*) for="VNC and the login screen" ;;
    esac
    while :; do
        new=$(whiptail --title "Password" --passwordbox \
"New password for $who. It is used for $for.

Cancel keeps the current password." 11 72 3>&1 1>&2 2>&3) || return 1
        if [ -z "$new" ]; then
            whiptail --title "Password" --msgbox \
                "The password cannot be empty. Type one, or choose Cancel." 8 64
            continue
        fi
        again=$(whiptail --title "Password" --passwordbox \
            "Type the new password again:" 9 72 3>&1 1>&2 2>&3) || return 1
        [ "$new" = "$again" ] && break
        whiptail --title "Password" --msgbox \
            "The two passwords are not the same. Nothing was changed: try again, or choose Cancel." 9 64
    done
    if err=$(printf '%s:%s\n' "$who" "$new" | sudo -n chpasswd 2>&1); then
        whiptail --title "Password" --msgbox "Password changed. Use the new one for $for." 8 72
        return 0
    fi
    whiptail --title "Password" --msgbox "The password was not changed.

$err" 12 72
    return 1
}

# ---------------------------------------------------------------------------
# Task (optional): about the bootloader firmware (EEPROM)
# ---------------------------------------------------------------------------
# rasqberry-firmware-check.service looks at start-up (rq_firmware.py): shown
# while an update is available and the firmware is older than about six
# months, or (Pi 5) its crypto service fails - which broke Raspberry Pi
# Connect from Imager. It only says how to update with Raspberry Pi's own
# tools: RasQberry never updates the firmware (Jan, 2026-10-07). Read once
# per firmware version.
FIRMWARE="${RQ_FIRMWARE:-$BIN_DIR/rq_firmware.py}"
FIRMWARE_READ_FILE="$STATE_DIR/firmware-info-read"
task_firmware_applies() { [ -x "$FIRMWARE" ] && "$FIRMWARE" due >/dev/null 2>&1; }
task_firmware_pending() { [ "$(cat "$FIRMWARE_READ_FILE" 2>/dev/null)" != "$("$FIRMWARE" line 2>/dev/null)" ]; }
task_firmware_label() {
    local date
    date=$("$FIRMWARE" line 2>/dev/null | sed 's/ (.*//')
    printf "Pi firmware from %s: a newer one is available" "${date:-an older release}"
}
task_firmware_run() {
    local text h
    text=$("$FIRMWARE" howto 2>/dev/null)
    h=$(( $(printf '%s\n' "$text" | fold -s -w 70 | wc -l) + 6 ))
    whiptail --title "Firmware" --msgbox "$text" "$h" 74
    mkdir -p "$STATE_DIR" 2>/dev/null && "$FIRMWARE" line > "$FIRMWARE_READ_FILE" 2>/dev/null
    return 0
}

# ---------------------------------------------------------------------------
# Task: keyboard layout and time zone (R-005)
# ---------------------------------------------------------------------------
# The image is set up for the UK. On a UK layout, US and German keyboards type
# some keys wrongly - in a Wi-Fi password, too - so this comes first. Pending
# while both are still the image's and the step was not answered.
LOCALE_DONE_FILE="$STATE_DIR/keyboard-timezone-set"
KEYBOARD_FILE="${RQ_KEYBOARD_FILE:-/etc/default/keyboard}"
TIMEZONE_FILE="${RQ_TIMEZONE_FILE:-/etc/timezone}"
kb_layout() { sed -n 's/^XKBLAYOUT="\{0,1\}\([^"]*\)"\{0,1\}/\1/p' "$KEYBOARD_FILE" 2>/dev/null | head -n 1; }
time_zone() { cat "$TIMEZONE_FILE" 2>/dev/null || echo unknown; }
task_locale_applies() { [ -f "$KEYBOARD_FILE" ]; }
task_locale_pending() {
    [ ! -e "$LOCALE_DONE_FILE" ] && [ "$(kb_layout)" = gb ] && [ "$(time_zone)" = "Europe/London" ]
}
task_locale_label() { printf 'Keyboard layout and time zone (set for the UK now)'; }
task_locale_run() {
    local layout zone
    layout=$(whiptail --title "Keyboard layout" --notags --default-item "$(kb_layout)" --menu \
        "Which keyboard is connected? Now: $(kb_layout)" 17 60 9 \
        gb "English (UK)" us "English (US)" de "German" fr "French" \
        es "Spanish" it "Italian" ch "Swiss" nl "Dutch" \
        other "Other: sudo raspi-config -> 5 Localisation Options" \
        3>&1 1>&2 2>&3) || return 0
    case "$layout" in
        other) ;;
        "$(kb_layout)") ;;
        *) sudo raspi-config nonint do_configure_keyboard "$layout" >/dev/null 2>&1 \
               || whiptail --title "Keyboard layout" --msgbox "Could not set the layout. Use: sudo raspi-config -> 5 Localisation Options" 8 72 ;;
    esac
    zone=$(time_zone)
    if whiptail --title "Time zone" --yes-button "Change" --no-button "Keep" --yesno \
        "The time zone is $zone. Change it?" 8 60; then
        sudo dpkg-reconfigure tzdata
    fi
    mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F' > "$LOCALE_DONE_FILE"
    [ "$layout" = other ] && whiptail --title "Keyboard layout" --msgbox \
        "For another layout: sudo raspi-config -> 5 Localisation Options -> Keyboard." 8 72
    return 0
}

# ---------------------------------------------------------------------------
# Task (optional): give this Pi its own name (R-063)
# ---------------------------------------------------------------------------
# Every card is called "rasqberry". With several kits on one network the
# later ones become rasqberry-2.local, -3 ... in no fixed order.
NAME_KEPT_FILE="$STATE_DIR/name-kept"
task_name_applies() { [ -x "$BIN_DIR/rq_remote_access.sh" ]; }
task_name_pending() { [ ! -e "$NAME_KEPT_FILE" ] && [ "$(hostname 2>/dev/null)" = rasqberry ]; }
task_name_label()   { printf 'Name this RasQberry (several kits on one network)'; }
task_name_run() {
    local old new out
    old=$(hostname 2>/dev/null)
    while true; do
        new=$(whiptail --title "Name this RasQberry" --ok-button "Rename" --cancel-button "Keep" --inputbox \
"With several kits on one network, give each its own name, e.g. rasqberry-01. Other computers then reach it as <name>.local.

Lowercase letters, digits and hyphens." 13 72 "$old" 3>&1 1>&2 2>&3) || new="$old"
        new=$(printf '%s' "$new" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
        if [ -z "$new" ] || [ "$new" = "$old" ]; then
            mkdir -p "$STATE_DIR" 2>/dev/null && date '+%F' > "$NAME_KEPT_FILE"
            return 0
        fi
        "$BIN_DIR/rq_remote_access.sh" check-name "$new" && break
        whiptail --title "Name this RasQberry" --msgbox \
            "'$new' cannot be used. Use lowercase letters, digits and hyphens, not at the start or end." 8 72
    done
    if out=$(sudo "$BIN_DIR/rq_remote_access.sh" name "$new" 2>&1); then
        whiptail --title "Name this RasQberry" --msgbox "$(printf '%s\n' "$out" | tail -n 1)" 8 72
    else
        whiptail --title "Name this RasQberry" --msgbox "The name was not changed:\n\n$out" 12 72
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Task: connect to Wi-Fi (only when there is no network at all)
# ---------------------------------------------------------------------------
task_wifi_applies() { [ -d "${RQ_WLAN_DIR:-/sys/class/net/wlan0}" ] && command -v nmtui >/dev/null 2>&1; }
task_wifi_pending() { ! ip route get 1.1.1.1 >/dev/null 2>&1; }
# The interface the internet goes through: wlan0, eth0 ...
net_dev() { ip route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | head -n 1; }
task_wifi_label()   { printf 'Connect to Wi-Fi (no network connection found)'; }
task_wifi_run()     { nmtui connect || sudo nmtui connect; }

# ---------------------------------------------------------------------------
# Task: download all demos now (they otherwise install on first use)
# ---------------------------------------------------------------------------
task_demos_applies() { [ -x "$BIN_DIR/rq_download_all.sh" ]; }
# Pending while a demo (the Docker demos aside) is not on the Pi. It looks at
# the demos themselves: the *_INSTALLED flags never counted Lights Out and
# Raspberry Tie, so the step stayed pending for good (R-087).
task_demos_pending() { "$BIN_DIR/rq_download_all.sh" --pending; }
task_demos_label()   { printf 'Download all demos now (or each one when first started)'; }
task_demos_run()     { "$BIN_DIR/rq_download_all.sh"; }

# ---------------------------------------------------------------------------
# Task: touch mode (only with a touchscreen attached)
# ---------------------------------------------------------------------------
# Enabling it restarts the desktop session, so it runs last (TASKS order).
task_touch_applies() {
    [ -x "$BIN_DIR/rq_touch_mode.sh" ] && grep -qiE 'touch|ft5x06|goodix|ili2' /proc/bus/input/devices 2>/dev/null
}
task_touch_pending() { [ "$("$BIN_DIR/rq_touch_mode.sh" status --quiet 2>/dev/null)" != "enabled" ]; }
task_touch_label()   { printf 'Touch mode: bigger icons and buttons (restarts the desktop)'; }
task_touch_run()     { "$BIN_DIR/rq_touch_mode.sh" enable --restart; }

# How a finished step reads in the --all list (R-134: "run again")
done_label() {
    case "$1" in
        wifi)
            # Truthfully: a Pi on a network cable is not on Wi-Fi (F3)
            case "$(net_dev)" in
                wl*)         echo "Run again: Wi-Fi (connected)" ;;
                eth*|en*)    echo "Set up Wi-Fi (the network is connected by cable now)" ;;
                *)           echo "Set up Wi-Fi (connected to a network now)" ;;
            esac ;;
        password) echo "Run again: password (keeping the demo password)" ;;
        locale)   echo "Run again: keyboard ($(kb_layout)) and time zone ($(time_zone))" ;;
        name)     echo "Run again: name ($(hostname 2>/dev/null))" ;;
        expand)   echo "Run again: SD card set up for A/B updates" ;;
        abinfo)   echo "Read again: about this SD card" ;;
        led)
            if [ "$(env_value LED_LAYOUT_VERIFIED)" = "skipped" ]; then
                echo "Run again: LED panel check (skipped: no panel)"
            else
                echo "Run again: LED panel check ($(led_layout_name "$(env_value LED_LAYOUT)"))"
            fi ;;
        demos)    echo "Run again: download all demos (done)" ;;
        firmware) echo "Read again: about the Pi's firmware" ;;
        touch)    echo "Run again: touch mode (on)" ;;
        *)        echo "Run again: $1" ;;
    esac
}

# Steps that are ticked when they are pending; the rest start unticked
# (rule 3). Wi-Fi only shows up without any network, so it is ticked too.
# The keyboard comes first: the Wi-Fi and the new password are typed on it.
# The password step shows up only while the account has the published demo
# password (no password set in Imager): ticked, so a click-through Run
# reaches its warning (Jan, user test 2026-10-07 F1). It still only asks:
# Esc or Cancel there changes nothing.
TICKED_TASKS="locale wifi password expand led"
is_ticked() { case " $TICKED_TASKS " in *" $1 "*) return 0 ;; esac; return 1; }

TASKS="locale wifi password name expand abinfo led demos firmware touch"

# Pending steps, one id per line
pending_tasks() {
    local t
    for t in $TASKS; do
        "task_${t}_applies" 2>/dev/null || continue
        if "task_${t}_pending" 2>/dev/null; then echo "$t"; fi
    done
    return 0
}

# ---------------------------------------------------------------------------
# --desktop: open the checklist ONCE, in its own window (Q12)
# ---------------------------------------------------------------------------
# Started by /etc/xdg/autostart/rasqberry-setup-checklist.desktop at every
# desktop login; does nothing after the first time.
#
# The IP address scroll (rasqberry-ip-display.service) waits for the network
# and then holds the LED panel for a minute or more. The checklist's LED check
# must not start under it (rule 2), so wait until the service has finished -
# and at least a little, so the browser that opens 10 s after login does not
# land on top of the checklist window.
wait_for_ip_display() {
    local waited=0 limit="${RQ_FIRSTLOGIN_WAIT:-300}" state
    sleep "${RQ_FIRSTLOGIN_MIN_WAIT:-15}"
    command -v systemctl >/dev/null 2>&1 || return 0
    while [ "$waited" -lt "$limit" ]; do
        state=$(systemctl show -p ActiveState --value rasqberry-ip-display.service 2>/dev/null)
        case "$state" in
            activating|deactivating|reloading) ;;
            *)
                # not started yet, still waiting for the network?
                systemctl list-jobs --no-legend 2>/dev/null | grep -q 'rasqberry-ip-display' || return 0 ;;
        esac
        sleep 5
        waited=$((waited + 5))
    done
    return 0
}

if [ "$MODE" = "desktop" ]; then
    already_shown && ! imager_note_pending && exit 0
    if [ -z "$(pending_tasks)" ] && ! imager_note_pending; then
        mark_shown
        mark_setup_done
        exit 0
    fi
    wait_for_ip_display
    # answered in an SSH login in the meantime
    already_shown && ! imager_note_pending && exit 0
    # Not marked here: only an answer counts (item 22). --now marks it.
    term=$(command -v lxterminal || command -v x-terminal-emulator) || exit 0
    exec "$term" -t "RasQberry Setup" -e \
        "bash -c '/usr/bin/rq_firstlogin.sh --now; echo; echo Press Enter to close this window...; read'"
fi

# The note about the user name first, once (not in --all). A login that
# came only for the note (the checklist was answered before) ends after it.
if [ "$MODE" != "all" ]; then
    show_imager_note
    [ "$MODE" = "login" ] && already_shown && exit 0
fi

# ---------------------------------------------------------------------------
# Collect what is pending
# ---------------------------------------------------------------------------
pending=""
args=()
for t in $TASKS; do
    "task_${t}_applies" 2>/dev/null || continue
    if "task_${t}_pending" 2>/dev/null; then
        state=OFF
        is_ticked "$t" && state=ON
        pending="$pending $t"
        args+=("$t" "$("task_${t}_label")" "$state")
    elif [ "$MODE" = "all" ]; then
        args+=("$t" "$(done_label "$t")" "OFF")
    fi
done

# Every step finished: done, the icon goes (also when the list was opened
# from the icon or the menu)
[ -z "$pending" ] && mark_setup_done

if [ -e "$HOME/Desktop/rasqberry-setup.desktop" ]; then
    REOPEN="Open this list again: the RasQberry Setup icon, or sudo raspi-config -> 0 RasQberry -> Setup Checklist."
else
    REOPEN="Open this list again: RasQberry Configuration (icon, or sudo raspi-config) -> 0 RasQberry -> Setup Checklist."
fi
# The last entry while the icon is there: done with the checklist for good
if ! setup_is_done && [ "$(id -u)" -ne 0 ]; then
    args+=("noicon" "Don't show again and remove the RasQberry Setup icon" "OFF")
fi

# Nothing to do: the login hook says nothing (it runs at a login); the window
# the desktop opened says so instead of standing empty.
if [ -z "$pending" ] && [ "$MODE" != "all" ]; then
    mark_shown
    mark_setup_done
    [ "$MODE" = "now" ] && echo "All setup steps are done."
    exit 0
fi

# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------
if [ "$MODE" = "all" ]; then
    if [ -z "$pending" ]; then
        text="All setup steps are done. Tick a step to run it again.

Space ticks or unticks a step, Enter runs the ticked ones."
    else
        text="Space ticks or unticks a step, Enter runs the ticked ones. Finished steps can be run again."
    fi
else
    text="Welcome to RasQberry Two! These steps finish the setup. Each takes a few minutes, and all of them can wait.

Space ticks or unticks a step, Enter runs the ticked ones.
$REOPEN"
fi
# Touchscreen without a keyboard (R-089)
if task_touch_applies 2>/dev/null; then
    text="$text
No keyboard? The keyboard icon in the top bar opens one on the screen."
fi
rows=$(( ${#args[@]} / 3 ))
# whiptail makes the list exactly as wide as its longest line, so that line
# touched the list's edge however short it was (437edbee shortened it; user
# test 2026-10-08, F4): a space after every line keeps a margin
for ((li = 1; li < ${#args[@]}; li += 3)); do
    args[li]="${args[li]} "
done
lines=$(printf '%s\n' "$text" | fold -s -w 72 | wc -l)
height=$(( rows + lines + 8 ))
max=$(tput lines 2>/dev/null || echo 24)
[ "$max" -ge 12 ] 2>/dev/null || max=24
[ "$height" -gt "$max" ] && height="$max"
wt_rc=0
choice=$(whiptail --title "RasQberry Two Setup" --notags --separate-output \
    --ok-button "Run" --cancel-button "Later" \
    --checklist "$text" "$height" 78 "$rows" "${args[@]}" 3>&1 1>&2 2>&3) || wt_rc=$?
# Run (0), Later (1) or Esc (255): a person answered. A window that was closed
# or a session that ended (killed by a signal) did not (item 22).
case "$wt_rc" in
    0|1|255) [ "$MODE" = "all" ] || mark_shown ;;
    *)       choice="" ;;
esac
[ "$wt_rc" -eq 0 ] || choice=""

if [ -z "$choice" ]; then
    [ "$MODE" = "all" ] || echo "$REOPEN"
    exit 0
fi

ran=false
touch_chosen=false
noicon=false
for sel in $choice; do
    # touch mode restarts the desktop, which closes this window: run it last
    if [ "$sel" = "touch" ]; then touch_chosen=true; continue; fi
    if [ "$sel" = "noicon" ]; then noicon=true; continue; fi
    "task_${sel}_run" || true
    ran=true
done

# Done with the checklist: every step finished, or "Don't show again"
gone="" gone_h=0
if ! setup_is_done && { [ "$noicon" = true ] || [ -z "$(pending_tasks)" ]; }; then
    mark_shown
    mark_setup_done
    gone="The RasQberry Setup icon is removed. This list stays in RasQberry Configuration -> 0 RasQberry -> Setup Checklist."
    REOPEN="" gone_h=1
fi
if [ "$ran" = false ] && [ -n "$gone" ]; then
    whiptail --title "RasQberry Two Setup" --msgbox "$gone" 9 74
fi

# Closing (R-088): where to start - the learning path for a first look,
# as on the website (#30)
if [ "$ran" = true ]; then
    # While the demo password is in place, say so once more (F1)
    pw_note="" pw_h=0
    if task_password_applies; then
        pw_note="

This Pi uses the published demo password: change it with passwd or in the RasQberry menu (Remote Access & Security)."
        pw_h=3
    fi
    whiptail --title "RasQberry Two Setup" --msgbox \
"Done. A good start: the learning path \"First 15 minutes\". It starts three demos for you and says what to try in each.

Double-click the Learning paths icon on the desktop, or: sudo raspi-config -> 0 RasQberry -> Quantum Demos -> Learning paths.

$REOPEN$gone$pw_note" $((15 + pw_h + gone_h)) 74
fi
if [ "$touch_chosen" = true ]; then
    task_touch_run || true
fi
exit 0
