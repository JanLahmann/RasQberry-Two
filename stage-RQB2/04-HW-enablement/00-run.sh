#!/bin/bash -e
# Enable SPI support.

on_chroot << EOF
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_spi 0 
EOF
