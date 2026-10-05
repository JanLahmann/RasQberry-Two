#!/usr/bin/env python3
"""
Unit tests for LED hand-overs between programs (user test 2026-10-05).

- Pi 4 (#1): a DMA transfer an earlier program left hanging under a stopped
  PWM is reset before the next driver starts; a frame that really goes out
  is left alone.

No hardware: /dev/mem is a sparse file, the driver backend a stand-in module.
"""

import os
import struct
import sys
import types

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_utils as lu  # noqa: E402

_DMA10 = lu._PI4_DMA_OFFSET + 10 * 0x100


@pytest.fixture
def pi4_regs(tmp_path, monkeypatch):
    """A stand-in /dev/mem (peripheral base 0) and the Pi 4 driver backend."""
    mem = tmp_path / "mem"
    with open(mem, "wb") as f:
        f.truncate(lu._PI4_PWM_OFFSET + 0x10000)
    real_open = os.open
    monkeypatch.setattr(lu.os, "open", lambda path, flags, *a: real_open(
        str(mem) if path == "/dev/mem" else path, os.O_RDWR if path == "/dev/mem" else flags, *a))
    monkeypatch.setattr(lu, "_soc_peripheral_base", lambda: 0)
    backend = types.ModuleType("adafruit_blinka.microcontroller.bcm283x.neopixel")
    backend._led_strip = None
    backend.LED_DMA_NUM = 10
    monkeypatch.setitem(sys.modules, "neopixel_write", types.SimpleNamespace(_neopixel=backend))

    def poke(offset, value):
        with open(mem, "r+b") as f:
            f.seek(offset)
            f.write(struct.pack("<I", value))

    def peek(offset):
        with open(mem, "rb") as f:
            f.seek(offset)
            return struct.unpack("<I", f.read(4))[0]

    return types.SimpleNamespace(poke=poke, peek=peek, backend=backend)


def _hanging(regs, pwm_ctl=0):
    """The rig's state after the LED check: DMA 10 busy towards the PWM."""
    regs.poke(_DMA10, 0x10ff0021)               # ACTIVE, waiting for the PWM
    regs.poke(_DMA10 + 8, 0x00050148)           # TI: PERMAP 5 = PWM
    regs.poke(lu._PI4_PWM_OFFSET, pwm_ctl)


def test_hanging_transfer_under_a_stopped_pwm_is_reset(pi4_regs):
    _hanging(pi4_regs)
    assert lu.recover_pi4_led_dma() is True
    assert pi4_regs.peek(_DMA10) == lu._PI4_DMA_RESET


def test_frame_going_out_is_left_alone(pi4_regs):
    _hanging(pi4_regs, pwm_ctl=0x2323)          # the PWM runs: a real frame
    assert lu.recover_pi4_led_dma() is False
    assert pi4_regs.peek(_DMA10) == 0x10ff0021


def test_idle_channel_and_other_transfers_are_left_alone(pi4_regs):
    pi4_regs.poke(_DMA10, 0x10ff000a)           # done (END)
    assert lu.recover_pi4_led_dma() is False
    _hanging(pi4_regs)
    pi4_regs.poke(_DMA10 + 8, 0x00070148)       # feeds another peripheral
    assert lu.recover_pi4_led_dma() is False
    assert pi4_regs.peek(_DMA10) == 0x10ff0021


def test_own_running_driver_and_other_boards_are_left_alone(pi4_regs, monkeypatch):
    _hanging(pi4_regs)
    pi4_regs.backend._led_strip = object()      # this program's driver runs
    assert lu.recover_pi4_led_dma() is False
    pi4_regs.backend._led_strip = None
    pi5 = types.ModuleType("adafruit_raspberry_pi5_neopixel_write")
    monkeypatch.setitem(sys.modules, "neopixel_write", types.SimpleNamespace(_neopixel=pi5))
    assert lu.recover_pi4_led_dma() is False
    assert pi4_regs.peek(_DMA10) == 0x10ff0021


def test_soc_peripheral_base_reads_the_device_tree(tmp_path, monkeypatch):
    ranges = tmp_path / "ranges"
    real_open = open

    def fake_open(path, *a, **k):
        return real_open(str(ranges) if path == "/proc/device-tree/soc/ranges" else path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open)
    ranges.write_bytes(bytes.fromhex("7e000000 00000000 fe000000 01800000"))   # Pi 4
    assert lu._soc_peripheral_base() == 0xFE000000
    ranges.write_bytes(bytes.fromhex("7e000000 3f000000 01000000"))            # Pi 3
    assert lu._soc_peripheral_base() == 0x3F000000
