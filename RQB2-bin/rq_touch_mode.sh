#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Touch Mode
# ============================================================================
# Description: Bigger panel icons, desktop icons, buttons and menus for a
#   touchscreen. The settings apply when the desktop restarts; restarting it
#   closes all windows, so this script never does that without being asked
#   (R-032). It restarts the display manager, which logs straight back in,
#   instead of ending the session, which left the password screen (R-149)
#   and could also end SSH logins.
# Usage:
#   rq_touch_mode.sh enable|disable|toggle            change it; applies at the next desktop login
#   rq_touch_mode.sh enable|disable|toggle --ask      ask first (a dialog on the desktop),
#                                                     then restart the desktop (the icon)
#   rq_touch_mode.sh enable|disable|toggle --restart  restart the desktop without asking
#   rq_touch_mode.sh status [--quiet]                 show the settings (or just enabled/disabled)
# Settings: TOUCH_* in /usr/config/rasqberry_environment.env.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"
load_rqb2_env
verify_env_vars USER_HOME

STATE_FILE="${RQ_TOUCH_STATE_FILE:-/var/lib/rasqberry/touch-mode.conf}"
GTK_CSS_SRC="/usr/config/touch-mode/gtk-touch.css"

TOUCH_PANEL_ICON_SIZE="${TOUCH_PANEL_ICON_SIZE:-48}"
TOUCH_DESKTOP_ICON_SIZE="${TOUCH_DESKTOP_ICON_SIZE:-72}"
# 12 pt at most: at 16 pt the RasQberry dialogs did not fit (R-033). On a
# screen lower than 600 px (the 7-inch display) the font stays as it is:
# even at 12 pt an 80x24 terminal runs off its bottom edge there.
TOUCH_TERMINAL_FONT_SIZE="${TOUCH_TERMINAL_FONT_SIZE:-12}"
[ "$TOUCH_TERMINAL_FONT_SIZE" -gt 12 ] 2>/dev/null && TOUCH_TERMINAL_FONT_SIZE=12
TOUCH_DOUBLE_CLICK_MS="${TOUCH_DOUBLE_CLICK_MS:-500}"
DEFAULT_PANEL_ICON_SIZE=24
DEFAULT_DESKTOP_ICON_SIZE=48
DEFAULT_DOUBLE_CLICK_MS=400

GTK_CSS_DST="$USER_HOME/.config/gtk-3.0/gtk.css"
LIBFM_CONFIG="$USER_HOME/.config/libfm/libfm.conf"
# The desktop icon size: bookworm's pcmanfm reads it from libfm.conf,
# trixie's pcmanfm-pi only from its profile's pcmanfm.conf ("default"; the
# profile as in rq_desktop_session.py). Both are set.
pcmanfm_profile() {
    local f p
    for f in "$USER_HOME/.config/labwc/autostart" /etc/xdg/labwc/autostart; do
        [ -f "$f" ] && grep -q pcmanfm "$f" || continue
        p=$(sed -n 's/.*pcmanfm .*--profile[ =]\([^ &]*\).*/\1/p' "$f" | head -1)
        echo "${p:-default}"
        return 0
    done
    echo default
}
PCMANFM_CONFIG="$USER_HOME/.config/pcmanfm/$(pcmanfm_profile)/pcmanfm.conf"
LXTERMINAL_CONFIG="$USER_HOME/.config/lxterminal/lxterminal.conf"
# wf-panel-pi's user config: ~/.config/wf-panel-pi/wf-panel-pi.ini on trixie
# (wf-panel-pi 1.x, defaults in /etc/xdg/wf-panel-pi/, read key by key),
# ~/.config/wf-panel-pi.ini on bookworm
if [ -f /etc/xdg/wf-panel-pi/wf-panel-pi.ini ] || [ -d "$USER_HOME/.config/wf-panel-pi" ]; then
    WF_PANEL_CONFIG="$USER_HOME/.config/wf-panel-pi/wf-panel-pi.ini"
else
    WF_PANEL_CONFIG="$USER_HOME/.config/wf-panel-pi.ini"
fi
# Older versions wrote here; Pi OS's Chromium never read it (R-098). The
# touch flag now comes from /etc/chromium.d/rasqberry.
OLD_CHROMIUM_FLAGS="$USER_HOME/.config/chromium-flags.conf.d/touch.conf"

DESKTOP_USER=$(get_user_name)

as_root() {
    if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo -n "$@"; fi
}

get_state() {
    local s
    s=$(sed -n 's/^TOUCH_MODE=//p' "$STATE_FILE" 2>/dev/null | tail -1) || true
    echo "${s:-disabled}"
}

# The desktop's screen height in pixels; empty without a running desktop
screen_height() {
    local uid run
    uid=$(id -u "$DESKTOP_USER" 2>/dev/null) || return 0
    run="/run/user/$uid"
    [ -S "$run/wayland-0" ] || return 0
    XDG_RUNTIME_DIR="$run" WAYLAND_DISPLAY=wayland-0 \
        python3 "$SCRIPT_DIR/rq_desktop_session.py" --screen 2>/dev/null | cut -dx -f2 || true
}

desktop_running() {
    systemctl is-active --quiet lightdm 2>/dev/null && pgrep -u "$DESKTOP_USER" -x labwc >/dev/null 2>&1
}

# Run a filter over FILE in place (keeps the file's owner and mode)
rewrite() {  # file command...
    local file="$1" tmp
    shift
    tmp=$(mktemp)
    "$@" < "$file" > "$tmp" && cat "$tmp" > "$file"
    rm -f "$tmp"
}

# Set KEY=VALUE in an ini-style file (added below [SECTION] if missing)
set_ini() {
    local file="$1" section="$2" key="$3" value="$4"
    [ -f "$file" ] || return 0
    if grep -q "^${key}=" "$file"; then
        rewrite "$file" awk -v k="$key" -v v="$value" 'index($0, k "=") == 1 { $0 = k "=" v } { print }'
    elif grep -qF "[${section}]" "$file"; then
        rewrite "$file" awk -v s="[${section}]" -v k="$key" -v v="$value" '{ print } $0 == s { print k "=" v }'
    fi
}

backup_once() {
    if [ -f "$1" ] && [ ! -f "$1.touch-backup" ]; then cp "$1" "$1.touch-backup"; fi
}

restore_or_set() {  # file section key default
    if [ -f "$1.touch-backup" ]; then
        mv "$1.touch-backup" "$1"
    else
        set_ini "$1" "$2" "$3" "$4"
    fi
}

write_state() {
    as_root mkdir -p "$(dirname "$STATE_FILE")"
    printf 'TOUCH_MODE=%s\nCHANGED_AT=%s\nCHANGED_BY=%s\n' "$1" "$(date -Iseconds)" "$DESKTOP_USER" \
        | as_root tee "$STATE_FILE" >/dev/null
}

fix_owner() {
    [ "$(id -u)" -eq 0 ] && [ "$DESKTOP_USER" != "root" ] || return 0
    local p
    for p in "$USER_HOME/.config/gtk-3.0" "$USER_HOME/.config/libfm" \
             "$USER_HOME/.config/lxterminal" "$WF_PANEL_CONFIG" "$PCMANFM_CONFIG"; do
        if [ -e "$p" ]; then chown -R "$DESKTOP_USER:" "$p"; fi
    done
}

enable_touch_mode() {
    local h
    if [ -f "$GTK_CSS_SRC" ]; then
        mkdir -p "$(dirname "$GTK_CSS_DST")"
        cp "$GTK_CSS_SRC" "$GTK_CSS_DST"   # again at every login: labwc-pi deletes it
    fi
    backup_once "$WF_PANEL_CONFIG"
    set_ini "$WF_PANEL_CONFIG" panel icon_size "$TOUCH_PANEL_ICON_SIZE"
    backup_once "$LIBFM_CONFIG"
    set_ini "$LIBFM_CONFIG" ui big_icon_size "$TOUCH_DESKTOP_ICON_SIZE"
    backup_once "$PCMANFM_CONFIG"
    set_ini "$PCMANFM_CONFIG" ui big_icon_size "$TOUCH_DESKTOP_ICON_SIZE"
    h=$(screen_height)
    if [ -n "$h" ] && [ "$h" -lt 600 ]; then
        info "Terminal font unchanged (small screen)."
    elif [ -f "$LXTERMINAL_CONFIG" ]; then
        backup_once "$LXTERMINAL_CONFIG"
        rewrite "$LXTERMINAL_CONFIG" sed "s/^\(fontname=.*\) [0-9][0-9]*$/\1 $TOUCH_TERMINAL_FONT_SIZE/"
    fi
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s "$TOUCH_DOUBLE_CLICK_MS" 2>/dev/null || true
    fi
    rm -f "$OLD_CHROMIUM_FLAGS"
    write_state enabled
    fix_owner
    info "Touch Mode is on: bigger panel and desktop icons, buttons and menus."
}

disable_touch_mode() {
    rm -f "$GTK_CSS_DST" "$OLD_CHROMIUM_FLAGS"
    restore_or_set "$WF_PANEL_CONFIG" panel icon_size "$DEFAULT_PANEL_ICON_SIZE"
    restore_or_set "$LIBFM_CONFIG" ui big_icon_size "$DEFAULT_DESKTOP_ICON_SIZE"
    restore_or_set "$PCMANFM_CONFIG" ui big_icon_size "$DEFAULT_DESKTOP_ICON_SIZE"
    if [ -f "$LXTERMINAL_CONFIG.touch-backup" ]; then
        mv "$LXTERMINAL_CONFIG.touch-backup" "$LXTERMINAL_CONFIG"
    fi
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s "$DEFAULT_DOUBLE_CLICK_MS" 2>/dev/null || true
    fi
    write_state disabled
    fix_owner
    info "Touch Mode is off: standard sizes."
}

# Ask before a restart: a dialog on the desktop (works with a finger), else a
# question in the terminal. Returns 1 for "no".
confirm() {  # target-state
    local verb="on" now="off" text answer
    if [ "$1" = "disabled" ]; then verb="off"; now="on"; fi
    text="Touch Mode is $now.\n\nTurn it $verb?"
    if [ "$verb" = "on" ]; then text="$text Bigger icons, buttons and menus for a touchscreen."; fi
    text="$text\n\nThe desktop restarts: all open windows close."
    if [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; then
        zenity --question --title "Touch Mode" --width 360 --text "$text" \
            --ok-label "Turn $verb" --cancel-label "Cancel" 2>/dev/null
        return
    fi
    [ -t 0 ] || return 1
    printf '%b\n\nTurn it %s and restart the desktop now? [y/N] ' "$text" "$verb"
    read -r answer || return 1
    case "$answer" in y|Y|yes|Yes) return 0 ;; esac
    return 1
}

# Restart the display manager: it logs the desktop user in again by itself
# (autologin), and SSH sessions stay.
restart_desktop() {
    if ! desktop_running; then
        info "The desktop is not running; the settings apply at the next desktop login."
        return 0
    fi
    info "Restarting the desktop..."
    as_root systemctl --no-block restart lightdm
}

change() {  # target-state restart-mode
    local target="$1" mode="$2"
    if [ "$mode" = "ask" ]; then
        if desktop_running; then
            confirm "$target" || { info "Nothing changed."; return 0; }
        fi
        mode="restart"
    fi
    if [ "$target" = "enabled" ]; then enable_touch_mode; else disable_touch_mode; fi
    if [ "$mode" = "restart" ]; then
        restart_desktop
    else
        info "Applies when the desktop restarts (or at the next login)."
    fi
}

show_status() {
    local state panel icons font
    state=$(get_state)
    if [ "${1:-}" = "--quiet" ] || [ "${1:-}" = "-q" ]; then
        echo "$state"
        return 0
    fi
    # (|| true: a missing file must not end the script under pipefail)
    panel=$(sed -n 's/^icon_size=//p' "$WF_PANEL_CONFIG" 2>/dev/null | head -1) || true
    icons=$(sed -n 's/^big_icon_size=//p' "$PCMANFM_CONFIG" "$LIBFM_CONFIG" 2>/dev/null | head -1) || true
    font=$(sed -n 's/^fontname=.* \([0-9][0-9]*\)$/\1/p' "$LXTERMINAL_CONFIG" 2>/dev/null | head -1) || true
    if [ "$state" = "enabled" ]; then echo "Touch Mode: ON"; else echo "Touch Mode: OFF"; fi
    echo
    echo "  Panel icons:    $( [ -n "$panel" ] && echo "$panel px" || echo default )"
    echo "  Desktop icons:  ${icons:-48} px"
    echo "  Terminal font:  ${font:-10} pt"
    echo
    echo "The keyboard icon in the top bar opens an on-screen keyboard."
}

usage() {
    echo "Usage: $(basename "$0") enable|disable|toggle [--ask|--restart] | status [--quiet]" >&2
    exit 1
}

cmd="${1:-}"
case "$cmd" in
    enable|on|disable|off|toggle)
        mode="none"
        case "${2:-}" in
            --ask) mode="ask" ;;
            --restart) mode="restart" ;;
            ""|--no-restart) ;;
            *) usage ;;
        esac
        case "$cmd" in
            enable|on) target="enabled" ;;
            disable|off) target="disabled" ;;
            *) target="enabled"; [ "$(get_state)" = "enabled" ] && target="disabled" ;;
        esac
        change "$target" "$mode"
        ;;
    status) show_status "${2:-}" ;;
    *) usage ;;
esac
