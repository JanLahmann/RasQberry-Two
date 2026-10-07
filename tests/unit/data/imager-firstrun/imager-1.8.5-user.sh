#!/bin/bash

set +e

CURRENT_HOSTNAME=`cat /etc/hostname | tr -d " \t\n\r"`
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname kit-07
else
   echo kit-07 >/etc/hostname
   sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\tkit-07/g" /etc/hosts
fi
FIRSTUSER=`getent passwd 1000 | cut -d: -f1`
FIRSTUSERHOME=`getent passwd 1000 | cut -d: -f6`
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh -k 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop'
else
   install -o "$FIRSTUSER" -m 700 -d "$FIRSTUSERHOME/.ssh"
   install -o "$FIRSTUSER" -m 600 <(printf "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop") "$FIRSTUSERHOME/.ssh/authorized_keys"
   echo 'PasswordAuthentication no' >>/etc/ssh/sshd_config
   systemctl enable ssh
fi
if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf 'jan' '$5$q6XMdhfKwxRP4DgV$6OHhYS0aGsYC3ZgKcVQzO6XEBLhHH8yQSf1Am3Vf3z9'
else
   echo "$FIRSTUSER:"'$5$q6XMdhfKwxRP4DgV$6OHhYS0aGsYC3ZgKcVQzO6XEBLhHH8yQSf1Am3Vf3z9' | chpasswd -e
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
	psk=1b6c3f1a2e5d8c7b9a0f1e2d3c4b5a69788766554433221100ffeeddccbbaa99
}

WPAEOF
   chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
   rfkill unblock wifi
   for filename in /var/lib/systemd/rfkill/*:wlan ; do
       echo 0 > $filename
   done
fi
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
