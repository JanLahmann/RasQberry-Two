#!/bin/bash
#
# patch /usr/bin/raspi-config and add RQB2 menu item
#

sudo patch -b --forward -r -  /usr/bin/raspi-config /usr/config/raspi-config.diff

