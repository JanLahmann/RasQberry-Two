#!/bin/bash -e
# Enable vnc server start at boot

on_chroot << EOF
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_vnc 0 
EOF
