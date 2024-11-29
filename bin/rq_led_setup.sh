#!/bin/sh
# setup of neopixel (https://docs.circuitpython.org/projects/neopixel_spi/en/latest/)
# to control the 48x24 LED Matrix

# install neopixel in venv
python3 -m venv /home/rasqberry/RasQberry-Two/venv/RQB2
source /home/rasqberry/RasQberry-Two/venv/RQB2/bin/activate
pip3 install adafruit-circuitpython-neopixel-spi

# Test via: /home/rasqberry/RasQberry-Two/venv/RQB2/bin/python /examples/neopixel_spi_IBMtestFunc.py
