#!/usr/bin/env python3
"""
Unit tests for the LED_WEB browser emulator (rq_led_web.py).

Pure-function / in-process tests: no GPIO, no real HTTP server bound to a public
port (read_frame is exercised directly, and the request handler is exercised via
its read_frame dependency). They pin the frame-bus decode + the (x, y) mapping so
the web view can never disagree with the physical strip or the Tk GUI.

Run with:
    python3 -m pytest tests/unit/ -q
"""

import os
import struct
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_utils as lu  # noqa: E402
import rq_led_web as web  # noqa: E402


# transport v2 constants mirrored from rq_led_virtual.py
_MAGIC = b'RQL1'
_PIXEL_OFFSET = 17


def _write_frame(path, width, height, pixels):
    """Write a transport-v2 mmap file with the given chain-order RGB pixels."""
    count = len(pixels)
    header = _MAGIC + struct.pack('<HHH', width, height, count) + b'\x00' * 6
    dirty = b'\x01'
    body = bytearray()
    for r, g, b in pixels:
        body += bytes((r, g, b))
    path.write_bytes(header + dirty + bytes(body))


@pytest.fixture
def frame_bus(tmp_path, monkeypatch):
    """Point rq_led_web at a temp frame-bus file and return its path."""
    p = tmp_path / "led.mmap"
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(p))
    return p


def test_read_frame_waiting_when_no_bus(frame_bus, monkeypatch):
    """No file / bad magic / zero geometry all read as 'waiting'."""
    monkeypatch.setattr(web, "_layout_name", lambda: "single-24x8")
    assert web.read_frame() == {"waiting": True}          # missing file
    frame_bus.write_bytes(b"XXXX" + b"\x00" * 20)          # bad magic
    assert web.read_frame() == {"waiting": True}


def test_read_frame_maps_chain_to_xy(frame_bus, monkeypatch):
    """Each logical (x, y) shows the colour written at its mapped chain index."""
    layout = "single-24x8"
    monkeypatch.setattr(web, "_layout_name", lambda: layout)

    pixels = [(0, 0, 0)] * 192
    marks = {(0, 0): (255, 0, 0), (23, 7): (0, 255, 0), (5, 3): (0, 0, 255)}
    for (x, y), c in marks.items():
        pixels[lu.map_xy_to_pixel(x, y, layout=layout)] = c
    _write_frame(frame_bus, 24, 8, pixels)

    frame = web.read_frame()
    assert (frame["w"], frame["h"], frame["layout"]) == (24, 8, layout)
    for (x, y), c in marks.items():
        assert frame["rows"][y][x] == list(c)
    assert frame["rows"][2][10] == [0, 0, 0]              # an unset cell is off


def test_read_frame_follows_layout_geometry(frame_bus, monkeypatch):
    """The decode honours the header geometry AND the configured layout map."""
    layout = "quad-4x12"
    monkeypatch.setattr(web, "_layout_name", lambda: layout)

    pixels = [(0, 0, 0)] * 192
    idx = lu.map_xy_to_pixel(12, 0, layout=layout)
    pixels[idx] = (10, 20, 30)
    _write_frame(frame_bus, 24, 8, pixels)

    frame = web.read_frame()
    assert frame["layout"] == "quad-4x12"
    assert frame["rows"][0][12] == [10, 20, 30]


def test_grid_cache_rebuilds_on_layout_change(frame_bus, monkeypatch):
    """Switching layout between reads must not serve a stale (x,y)->chain grid."""
    pixels = [(0, 0, 0)] * 192
    pixels[lu.map_xy_to_pixel(1, 0, layout="single-24x8")] = (1, 2, 3)
    _write_frame(frame_bus, 24, 8, pixels)

    monkeypatch.setattr(web, "_layout_name", lambda: "single-24x8")
    f1 = web.read_frame()
    monkeypatch.setattr(web, "_layout_name", lambda: "quad-4x12")
    f2 = web.read_frame()
    # Same bytes, different layout -> different decoded grids (cache keyed on layout)
    assert f1["layout"] != f2["layout"]
    assert f1["rows"] != f2["rows"]
