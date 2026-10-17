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

# balena wifi-connect (Apache-2.0) for the setup hotspot (rq_setup_hotspot.sh):
# a new Pi without a network opens a Wi-Fi whose page joins the user's Wi-Fi.
# A pinned release, checked against its SHA-256; the page is RasQberry's own
# (/usr/share/rasqberry/setup-portal, from RQB2-system), and so is its licence
# text (/usr/share/doc/wifi-connect/copyright; Apache-2.0 4a).
WIFI_CONNECT_VERSION=v4.11.90
WIFI_CONNECT_SHA256=4b2321e61895ab1afed5125ed70276845fcb48967e647454812ae336020ce14e
wc_tmp=$(mktemp -d)
curl -fsSL --retry 4 --retry-delay 10 --retry-connrefused -o "$wc_tmp/wc.tar.gz" \
  "https://github.com/balena-os/wifi-connect/releases/download/${WIFI_CONNECT_VERSION}/wifi-connect-aarch64-unknown-linux-gnu.tar.gz"
echo "${WIFI_CONNECT_SHA256}  $wc_tmp/wc.tar.gz" | sha256sum -c -
tar -xzf "$wc_tmp/wc.tar.gz" -C "$wc_tmp" wifi-connect
install -m 755 "$wc_tmp/wifi-connect" /usr/local/sbin/wifi-connect
rm -rf "$wc_tmp"
echo "wifi-connect ${WIFI_CONNECT_VERSION} installed"

echo "System integration configured"
