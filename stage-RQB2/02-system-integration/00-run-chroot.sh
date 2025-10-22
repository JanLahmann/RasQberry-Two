#!/bin/bash -e

echo "Configuring system integration (cron jobs, patches)"

# Apply RQB2 patch to /usr/bin/raspi-config at boot time
# Adding patch script to root-crontab
bash -c 'CRON="@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'

# Add hardware detection script to root-crontab (runs at every boot)
# This ensures PI_MODEL is always current, even if SD card is moved between Pi models
bash -c 'CRON="@reboot /usr/bin/rq_detect_hardware.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'

echo "System integration configured"
