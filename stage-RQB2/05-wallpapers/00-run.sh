#!/bin/bash -e

# skip this File for workflow testing
#exit 0

# TODO: Improve error checking. 
#       Handle a CONF_DIR that is present but has incorrect ownership/permissions
#       Use the higher resolution image for HDMI.

# Define variables for the wallpaper image fine name, source and destination.
# Both WP_DIR and RQPI_DIR must exist, and RQPI_DIR must contain our wallpaper files.
CONF_DIR=$ROOTFS_DIR/home/$FIRST_USER_NAME/.config/pcmanfm/LXDE-pi
RQPI_DIR=$ROOTFS_DIR/home/$FIRST_USER_NAME/.local/config/Artwork/Logo-Wallpaper
WP_DIR=/usr/share/rpd-wallpaper
WALLPAPER='RasQberry 2 Wallpaper FHD.png'

# Ugly hack #1 for build environments where the username for uid 1000 is not $FIRST_USER_NAME.
FIRST_UID=1000

# Config file for HDMI-attached screen.
HDMI_CONF=desktop-items-HDMI-A-1.conf

# Config file for headless operation
NOOP_CONF=desktop-items-NOOP-1.conf

CONF_FILES=($NOOP_CONF $HDMI_CONF)

# Ensure CONF_DIR is present.
if ! [ -e $CONF_DIR ]; then
    sudo -u "#${FIRST_UID}" mkdir -p "$CONF_DIR"
fi

# Ensure source and destination directories exist.

if ! [[ -e $RQPI_DIR && -e $ROOTFS_DIR/$WP_DIR ]]; then
    echo "The environment is not properly set up. The source and/or target directory is missing. Exiting."
    exit 1    
fi

# Check that the wallpaper file is present.
if ! [ -e $RQPI_DIR/"$WALLPAPER" ]; then
    echo "The chosen wallpaper $WALLPAPER is not present in $RQPI_DIR. Exiting."
    exit 1
fi

# Copy the background image to the image's WP_DIR.
if ! [ -e $ROOTFS_DIR/$WP_DIR/"$WALLPAPER" ]; then
    sudo cp $RQPI_DIR/"$WALLPAPER" $ROOTFS_DIR/$WP_DIR

    # Ugly hack #2. Fix incorrect permissions on the asset
    sudo chmod 644 $ROOTFS_DIR/$WP_DIR/"$WALLPAPER"
fi
 
# Ensure CONF_DIR is writable
if ! [ -w "$CONF_DIR" ]; then 
    echo "Configuration file destination is not writable. Cannot continue." 
	exit 1
fi

echo "Generating config files."

for configfile in "${CONF_FILES[@]}"; do
  if [ -e $CONF_DIR/$configfile ]; then
    echo "$CONF_DIR/$configfile already exists. Attempting to update wallpaper selection."
    sudo -u "#${FIRST_UID}" sed $CONF_DIR/$configfile -i -e "/^wallpaper=/{h;s/=.*/=${WP_DIR//\//\\/}\/${WALLPAPER}/};\${x;/^$/{s//wallpaper=${WP_DIR//\//\\/}\/${WALLPAPER}/;H};x}" 
    echo "File $configfile updated."
  else
    sudo -u "#${FIRST_UID}" touch $CONF_DIR/$configfile
    sudo -u "#${FIRST_UID}" cat <<EOF >> $CONF_DIR/$configfile
[*]
wallpaper_mode=fit
wallpaper=$WP_DIR/$WALLPAPER
EOF

    echo "File $configfile updated."
  fi
done
