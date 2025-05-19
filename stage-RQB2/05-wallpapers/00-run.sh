#!/bin/sh -e
#
# pi-gen stage to install a custom wallpaper and set it as default
#

# variables provided by pi-gen
# ROOTFS_DIR — root of the target filesystem
# FIRST_USER_NAME — usually “pi”
# (you could also detect a non-root account via getent)

WALLPAPER_SRC="$(dirname "$0")/files/RasQberry 2 Wallpaper 4K.png"
WALLPAPER_NAME="RasQberry 2 Wallpaper 4K.png"

# where Pi OS stores its collection of wallpapers
SYS_WP_DIR="$ROOTFS_DIR/usr/share/rpd-wallpaper"

# PCManFM global config directory
PCMAN_CONF_DIR="$ROOTFS_DIR/etc/xdg/pcmanfm/LXDE-pi"

echo "=> Installing custom wallpaper to $SYS_WP_DIR"
install -v -m 644 "$WALLPAPER_SRC" \
  "$SYS_WP_DIR/$WALLPAPER_NAME"

echo "=> Ensuring PCManFM global config dir exists"
mkdir -p "$PCMAN_CONF_DIR"

# for primary console (usually desktop-items-0) and HDMI (desktop-items-1)
for CONF in desktop-items-0.conf desktop-items-1.conf; do
  TARGET="$PCMAN_CONF_DIR/$CONF"
  if [ -f "$TARGET" ]; then
    echo " * Updating existing $CONF"
    sed -i \
      "s|^wallpaper=.*|wallpaper=/usr/share/rpd-wallpaper/$WALLPAPER_NAME|" \
      "$TARGET"
  else
    echo " * Creating new $CONF"
    cat <<EOF > "$TARGET"
[*]
wallpaper_mode=fit
wallpaper=/usr/share/rpd-wallpaper/$WALLPAPER_NAME
EOF
  fi
  # make sure it's owned by root
  chown 0:0 "$TARGET"
done

echo "=> Wallpaper stage complete"