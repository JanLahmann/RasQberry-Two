#!/bin/bash
#
# patch /usr/bin/raspi-config and add RQB2 menu item
#

/usr/bin/patch -b --forward -r -  /usr/bin/raspi-config /usr/config/raspi-config.diff

