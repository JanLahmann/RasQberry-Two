#!/bin/bash -e

echo "=> Checking RasQberry A/B boot support"

# The A/B scripts are installed to /usr/bin by 01-deploy-files, and the
# health-check and tryboot-retry units are installed and enabled from
# RQB2-system/ by the same stage (#294). This stage only verifies them.
missing=0
for script in rq_health_check.py rq_slot_manager.sh rq_common.sh rq_update_slot.sh rq_tryboot_retry.sh \
              rq_expand_ab.sh rq_carry_over.sh rq_after_update.sh; do
    if [ ! -f "/usr/bin/$script" ]; then
        echo "ERROR: /usr/bin/$script not found"
        missing=1
    fi
done
for unit in rasqberry-health-check.service rasqberry-tryboot-retry.service \
            rasqberry-ab-layout.service rasqberry-carry-over.service rasqberry-probation.timer \
            rasqberry-after-update.service; do
    # the enablement symlink (no running systemd in the build chroot)
    ls /etc/systemd/system/*.wants/"$unit" >/dev/null 2>&1 || { echo "ERROR: $unit is not enabled"; missing=1; }
done
[ "$missing" -eq 0 ] || exit 1

echo "=> A/B boot support present: health check, tryboot retry, first-start card"
echo "   layout, carry-over and the probation deadline are enabled."
echo "   The A/B layout itself is created after the build (convert-to-ab-boot-v3.sh)."
echo "   rasqberry-update-poller.timer ships disabled (rig/dev tool); the daily"
echo "   rasqberry-update-check.timer only reports new releases."
