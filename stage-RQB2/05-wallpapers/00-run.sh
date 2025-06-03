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
      -e "s|^wallpaper=.*|wallpaper=/usr/share/rpd-wallpaper/$WALLPAPER_NAME|" \
      -e "s|^desktop_fg=.*|desktop_fg=#000000|" \
      -e "s|^desktop_bg=.*|desktop_bg=#FFFFFF|" \
      -e "s|^desktop_shadow=.*|desktop_shadow=#FFFFFF|" \
      -e "s|^shadow_x=.*|shadow_x=1|" \
      -e "s|^shadow_y=.*|shadow_y=1|" \
      "$TARGET"
    
    # Add the desktop text settings if they don't exist
    if ! grep -q "^desktop_fg=" "$TARGET"; then
      echo "desktop_fg=#000000" >> "$TARGET"
    fi
    if ! grep -q "^desktop_bg=" "$TARGET"; then
      echo "desktop_bg=#FFFFFF" >> "$TARGET"
    fi
    if ! grep -q "^desktop_shadow=" "$TARGET"; then
      echo "desktop_shadow=#FFFFFF" >> "$TARGET"
    fi
    if ! grep -q "^shadow_x=" "$TARGET"; then
      echo "shadow_x=1" >> "$TARGET"
    fi
    if ! grep -q "^shadow_y=" "$TARGET"; then
      echo "shadow_y=1" >> "$TARGET"
    fi
  else
    echo " * Creating new $CONF"
    cat <<EOF > "$TARGET"
[*]
wallpaper_mode=fit
wallpaper=/usr/share/rpd-wallpaper/$WALLPAPER_NAME
desktop_fg=#000000
desktop_bg=#FFFFFF
desktop_shadow=#FFFFFF
shadow_x=1
shadow_y=1
EOF
  fi
  # make sure it's owned by root
  chown 0:0 "$TARGET"
done

echo "=> Wallpaper stage complete"