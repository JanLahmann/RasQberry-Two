#!/bin/sh

set +e

CURRENT_HOSTNAME=$(cat /etc/hostname | tr -d " \t\n\r")
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname kit-07
else
   echo kit-07 >/etc/hostname
   sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\tkit-07/g" /etc/hosts
fi
FIRSTUSER=$(getent passwd 1000 | cut -d: -f1)
FIRSTUSERHOME=$(getent passwd 1000 | cut -d: -f6)
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh -k 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop'
else
   install -o "$FIRSTUSER" -m 700 -d "$FIRSTUSERHOME/.ssh"
cat > "$FIRSTUSERHOME/.ssh/authorized_keys" <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop
EOF
   chown "$FIRSTUSER:$FIRSTUSER" "$FIRSTUSERHOME/.ssh/authorized_keys"
   chmod 600 "$FIRSTUSERHOME/.ssh/authorized_keys"
   echo 'PasswordAuthentication no' >>/etc/ssh/sshd_config
   systemctl enable ssh
fi
if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf 'jan' '$5$q6XMdhfKwxRP4DgV$6OHhYS0aGsYC3ZgKcVQzO6XEBLhHH8yQSf1Am3Vf3z9'
else
   echo "$FIRSTUSER:$5$q6XMdhfKwxRP4DgV$6OHhYS0aGsYC3ZgKcVQzO6XEBLhHH8yQSf1Am3Vf3z9" | chpasswd -e
   if [ "$FIRSTUSER" != "jan" ]; then
      usermod -l "jan" "$FIRSTUSER"
      usermod -m -d "/home/jan" "jan"
      groupmod -n "jan" "$FIRSTUSER"
      if grep -q "^autologin-user=" /etc/lightdm/lightdm.conf ; then
         sed /etc/lightdm/lightdm.conf -i -e "s/^autologin-user=.*/autologin-user=jan/"
      fi
      if [ -f /etc/systemd/system/getty@tty1.service.d/autologin.conf ]; then
         sed /etc/systemd/system/getty@tty1.service.d/autologin.conf -i -e "s/$FIRSTUSER/jan/"
      fi
      if [ -f /etc/sudoers.d/010_pi-nopasswd ]; then
         sed -i "s/^$FIRSTUSER /jan /" /etc/sudoers.d/010_pi-nopasswd
      fi
   fi
fi
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_wlan 'Classroom' '1b6c3f1a2e5d8c7b9a0f1e2d3c4b5a69788766554433221100ffeeddccbbaa99' 'DE'
else
cat >/etc/wpa_supplicant/wpa_supplicant.conf <<'WPAEOF'
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1

update_config=1
network={
	ssid="Classroom"
	key_mgmt=WPA-PSK SAE
	psk=1b6c3f1a2e5d8c7b9a0f1e2d3c4b5a69788766554433221100ffeeddccbbaa99
	ieee80211w=1
}
WPAEOF
   chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
   rfkill unblock wifi
   for filename in /var/lib/systemd/rfkill/*:wlan ; do
       echo 0 > $filename
   done
fi
TARGET_USER="jan"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [ -z "$TARGET_HOME" ] || [ ! -d "$TARGET_HOME" ]; then TARGET_HOME="/home/jan"; fi
install -o "$TARGET_USER" -m 700 -d "$TARGET_HOME/.config/com.raspberrypi.connect"
cat > "$TARGET_HOME/.config/com.raspberrypi.connect/auth.key" <<'EOF'
rpuak_TESTTOKENaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
EOF
chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/com.raspberrypi.connect/auth.key"
chmod 600 "$TARGET_HOME/.config/com.raspberrypi.connect/auth.key"
# Enable Raspberry Pi Connect systemd units
SYSTEMD_USER_BASE="$TARGET_HOME/.config/systemd/user"
install -o "$TARGET_USER" -m 700 -d "$SYSTEMD_USER_BASE/default.target.wants" "$SYSTEMD_USER_BASE/paths.target.wants"
UNIT_SRC="/usr/lib/systemd/user/rpi-connect.service"; [ -f "$UNIT_SRC" ] || UNIT_SRC="/lib/systemd/user/rpi-connect.service"
ln -sf "$UNIT_SRC" "$SYSTEMD_USER_BASE/default.target.wants/rpi-connect.service"
UNIT_SRC="/usr/lib/systemd/user/rpi-connect-signin.path"; [ -f "$UNIT_SRC" ] || UNIT_SRC="/lib/systemd/user/rpi-connect-signin.path"
ln -sf "$UNIT_SRC" "$SYSTEMD_USER_BASE/paths.target.wants/rpi-connect-signin.path"
UNIT_SRC="/usr/lib/systemd/user/rpi-connect-wayvnc.service"; [ -f "$UNIT_SRC" ] || UNIT_SRC="/lib/systemd/user/rpi-connect-wayvnc.service"
ln -sf "$UNIT_SRC" "$SYSTEMD_USER_BASE/default.target.wants/rpi-connect-wayvnc.service"
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/systemd" || true
install -d -m 0755 /var/lib/systemd/linger
install -m 0644 /dev/null "/var/lib/systemd/linger/$TARGET_USER"
loginctl enable-linger "$TARGET_USER" 2>/dev/null || true
# Give user manager time to start if it wasn't already running
sleep 2
# Reload user systemd manager and start services
systemctl --quiet --user --machine ${TARGET_USER}@.host daemon-reload
systemctl --quiet --user --machine ${TARGET_USER}@.host start rpi-connect.service rpi-connect-signin.path rpi-connect-wayvnc.service
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_keymap 'de'
   /usr/lib/raspberrypi-sys-mods/imager_custom set_timezone 'Europe/Berlin'
else
   rm -f /etc/localtime
   echo "Europe/Berlin" >/etc/timezone
   dpkg-reconfigure -f noninteractive tzdata
cat >/etc/default/keyboard <<'KBEOF'
XKBMODEL="pc105"
XKBLAYOUT="de"
XKBVARIANT=""
XKBOPTIONS=""

KBEOF
   dpkg-reconfigure -f noninteractive keyboard-configuration
fi
rm -f /boot/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt
exit 0
