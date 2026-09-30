#!/bin/bash -e

# ============================================================================
# Enable memory cgroups on the kernel command line
# ============================================================================
# Docker's per-container memory limits (--memory / --memory-swap) are SILENTLY
# discarded by the Raspberry Pi kernel unless memory cgroups are enabled on the
# kernel command line. Without them, only --cpus / --pids-limit take effect - so
# the multi-user doQumentation ("Workshop Server") profiles (2/8/15 users) would
# have no memory/OOM protection. Add the two required parameters here.
#
# This runs host-side (edits ${ROOTFS_DIR}/boot/firmware/cmdline.txt) after the
# base cmdline edits (stage 00 serial console) and BEFORE the A/B boot conversion
# (stage 08), whose PRESERVED_PARAMS step copies arbitrary cmdline parameters
# into both slots - so a single edit here reaches slot A and slot B.
#
# Idempotent: only appends parameters that are not already present.

CMDLINE_TXT="${ROOTFS_DIR}/boot/firmware/cmdline.txt"

if [ ! -f "$CMDLINE_TXT" ]; then
    echo "ERROR: cmdline.txt not found at $CMDLINE_TXT"
    exit 1
fi

echo "=> Enabling memory cgroups in cmdline.txt (for Docker --memory limits)"
CMDLINE=$(cat "$CMDLINE_TXT")

for param in cgroup_enable=memory cgroup_memory=1; do
    case " $CMDLINE " in
        *" $param "*) echo "   already present: $param" ;;
        *)            CMDLINE="$CMDLINE $param"; echo "   added: $param" ;;
    esac
done

# Collapse any double spaces and write back.
CMDLINE=$(echo "$CMDLINE" | sed 's/  */ /g')
echo "$CMDLINE" > "$CMDLINE_TXT"

echo "Final cmdline.txt:"
cat "$CMDLINE_TXT"
