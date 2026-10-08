#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: keep the SSH identity across an A/B slot update (#275)
# ============================================================================
# Description: Each slot has its own root filesystem, so a slot written by
#   rq_update_slot.sh came up with a new SSH host key (clients refuse with
#   "REMOTE HOST IDENTIFICATION HAS CHANGED") and without the user's
#   authorized_keys (key login fails). This copies both from the running slot
#   into the freshly written target root, device to device, at update time.
#   Nothing is baked into the published image: every device still generates
#   its own keys on its first boot.
#
#   Carried over, and nothing else: /etc/ssh/ssh_host_*, the desktop
#   user's ~/.ssh/authorized_keys, and a "PasswordAuthentication no" choice
#   (Imager's "public-key only" writes it into sshd_config; a freshly written
#   slot would allow password login again).
#
#   The stock regenerate_ssh_host_keys.service deletes all host keys on the
#   first boot of a flashed image, unconditionally; it is masked in the target
#   so the copied keys survive. A later package upgrade cannot re-enable a
#   masked unit.
#
# Usage: rq_carry_ssh_identity.sh <mounted-target-root>   (as root)
# Called by rq_update_slot.sh; a failure there is a warning, not an abort.
#
# Environment overrides (tests): RQ_SSH_SOURCE_ROOT (default /),
#   RQ_SSH_USER_HOME (default: home of uid 1000)

target="${1:-}"
[ -n "$target" ] && [ -d "$target/etc" ] || { echo "Usage: $(basename "$0") <mounted-target-root>" >&2; exit 2; }
src="${RQ_SSH_SOURCE_ROOT:-}"
home="${RQ_SSH_USER_HOME:-$(getent passwd 1000 2>/dev/null | cut -d: -f6)}"
# The new slot's own desktop user: a fresh image has "rasqberry" while this
# system's user may have been renamed (#319); its first start renames it, and
# the keys move along with the home folder
tgt_home=$(awk -F: '$3 == 1000 { print $6; exit }' "$target/etc/passwd" 2>/dev/null || true)
tgt_home="${tgt_home:-$home}"
carried=""

# Host keys
if compgen -G "$src/etc/ssh/ssh_host_*_key" >/dev/null && [ -d "$target/etc/ssh" ]; then
    rm -f "$target"/etc/ssh/ssh_host_*
    cp -p "$src"/etc/ssh/ssh_host_* "$target/etc/ssh/"
    chmod 600 "$target"/etc/ssh/ssh_host_*_key
    chmod 644 "$target"/etc/ssh/ssh_host_*_key.pub
    mkdir -p "$target/etc/systemd/system"
    ln -sfn /dev/null "$target/etc/systemd/system/regenerate_ssh_host_keys.service"
    rm -f "$target/etc/systemd/system/multi-user.target.wants/regenerate_ssh_host_keys.service"
    carried="host keys"
fi

# The user's authorized_keys
if [ -n "$home" ] && [ -s "$src$home/.ssh/authorized_keys" ] && [ -d "$target$tgt_home" ]; then
    mkdir -p "$target$tgt_home/.ssh"
    cp "$src$home/.ssh/authorized_keys" "$target$tgt_home/.ssh/authorized_keys"
    chmod 700 "$target$tgt_home/.ssh"
    chmod 600 "$target$tgt_home/.ssh/authorized_keys"
    if [ "$(id -u)" = "0" ]; then
        owner=$(stat -c %u:%g "$target$tgt_home")
        chown "$owner" "$target$tgt_home/.ssh" "$target$tgt_home/.ssh/authorized_keys"
    fi
    carried="${carried:+$carried and }authorized_keys"
fi

# The password-login choice. sshd keeps the first value it reads, and Debian's
# sshd_config includes sshd_config.d/*.conf at its top, so drop-ins come first
pw_auth=$(cat "$src"/etc/ssh/sshd_config.d/*.conf "$src/etc/ssh/sshd_config" 2>/dev/null \
    | awk 'tolower($1) == "passwordauthentication" { print tolower($2); exit }' || true)
if [ "$pw_auth" = "no" ] && [ -d "$target/etc/ssh" ]; then
    mkdir -p "$target/etc/ssh/sshd_config.d"
    printf '%s\n' "# Carried over by RasQberry's A/B update: password login stays off" \
        "PasswordAuthentication no" > "$target/etc/ssh/sshd_config.d/00-rasqberry-carried.conf"
    chmod 644 "$target/etc/ssh/sshd_config.d/00-rasqberry-carried.conf"
    carried="${carried:+$carried and }password login off"
fi

echo "SSH identity carried over: ${carried:-nothing (no host keys or authorized_keys found)}"
