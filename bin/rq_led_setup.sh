#!/bin/sh
# setup of neopixel (https://docs.circuitpython.org/projects/neopixel_spi/en/latest/)
# to control the 48x24 LED Matrix

# install neopixel in venv
python3 -m venv .venv
source .venv/bin/activate
pip3 install adafruit-circuitpython-neopixel-spi

# Test via: .venv/bin/python /examples/neopixel_spi_IBMtestFunc.py
