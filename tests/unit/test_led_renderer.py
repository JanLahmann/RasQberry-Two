#!/usr/bin/env python3
"""
Unit tests for the RasQberry root-confined LED renderer (Phase A2).

These run WITHOUT hardware: the neopixel/board imports live inside
LedRenderer.create_strip() only, so importing rq_led_renderer and exercising
its mmap frame-extraction (parse_header / read_frame) needs no GPIO. The
transport path is redirected to a temp file via RQB2_LED_MMAP_PATH, and the
real VirtualNeoPixel is used as the writer so the writer/reader handshake is
tested end to end against the actual on-disk format.

Run with:
    python3 -m pytest tests/unit/ -q
"""

import mmap
import os
import sys

import pytest

# Make RQB2-bin importable (rq_led_renderer / rq_led_virtual live there).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_renderer as rr  # noqa: E402
import rq_led_virtual as rv  # noqa: E402


WIDTH, HEIGHT = 24, 8
COUNT = WIDTH * HEIGHT  # 192


@pytest.fixture
def mmap_file(tmp_path, monkeypatch):
    """Point both writer and renderer at a private temp mmap path."""
    path = str(tmp_path / "led.mmap")
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(path))
    return path


def _writer(brightness=1.0):
    """A VirtualNeoPixel writer with explicit geometry (no config lookups)."""
    return rv.VirtualNeoPixel(
        None, COUNT, brightness=brightness, auto_write=False,
        pixel_order="GRB", width=WIDTH, height=HEIGHT,
    )


def _open_reader(path):
    """Open a read/write mmap of the transport file, like the renderer does."""
    f = open(path, "r+b")
    mm = mmap.mmap(f.fileno(), 0)
    return f, mm


def test_env_override_directs_writer_to_temp_file(mmap_file):
    """RQB2_LED_MMAP_PATH must redirect the writer off the default /tmp path."""
    assert rv.mmap_path() == mmap_file
    w = _writer()
    try:
        assert os.path.exists(mmap_file)
    finally:
        w.deinit()


def test_header_parse(mmap_file):
    """parse_header reads back the geometry the writer wrote."""
    w = _writer()
    try:
        f, mm = _open_reader(mmap_file)
        try:
            magic, width, height, count = rr.parse_header(mm)
            assert magic == rr.MMAP_MAGIC
            assert (width, height, count) == (WIDTH, HEIGHT, COUNT)
        finally:
            mm.close()
            f.close()
    finally:
        w.deinit()


def test_dirty_flag_handshake(mmap_file):
    """read_frame returns a frame only while dirty, then clears the flag."""
    w = _writer()
    try:
        f, mm = _open_reader(mmap_file)
        try:
            # Fresh file: not dirty yet.
            assert rr.read_frame(mm) is None

            w.fill((10, 20, 30))
            w.show()  # sets the dirty byte + payload

            first = rr.read_frame(mm)
            assert first is not None
            assert len(first) == COUNT

            # Flag was consumed -> second read is None until the next show().
            assert rr.read_frame(mm) is None

            w.show()
            assert rr.read_frame(mm) is not None
        finally:
            mm.close()
            f.close()
    finally:
        w.deinit()


def test_round_trip_values_verbatim_at_full_brightness(mmap_file):
    """At brightness 1.0 the frame the renderer reads equals what was written."""
    w = _writer(brightness=1.0)
    try:
        w[0] = (255, 0, 0)
        w[1] = (0, 255, 0)
        w[2] = (0, 0, 255)
        w[COUNT - 1] = (12, 34, 56)
        w.show()

        f, mm = _open_reader(mmap_file)
        try:
            frame = rr.read_frame(mm)
        finally:
            mm.close()
            f.close()

        assert frame[0] == (255, 0, 0)
        assert frame[1] == (0, 255, 0)
        assert frame[2] == (0, 0, 255)
        assert frame[COUNT - 1] == (12, 34, 56)
        assert frame[3] == (0, 0, 0)
    finally:
        w.deinit()


def test_writer_pre_applies_brightness(mmap_file):
    """
    Confirms the brightness pre-application the renderer relies on.

    The writer attenuates RGB by brightness BEFORE writing the mmap, so the
    renderer must drive the strip at brightness 1.0 (no second attenuation).
    """
    w = _writer(brightness=0.5)
    try:
        w[0] = (200, 100, 50)
        w.show()

        f, mm = _open_reader(mmap_file)
        try:
            frame = rr.read_frame(mm)
        finally:
            mm.close()
            f.close()

        # 0.5 pre-applied by the writer: int(200*0.5)=100, etc.
        assert frame[0] == (100, 50, 25)
    finally:
        w.deinit()


def test_configured_geometry_from_layout(mmap_file):
    """LedRenderer derives geometry from the layout registry when config lacks it."""
    renderer = rr.LedRenderer({'led_layout': 'single-8x32', 'led_count': 999})
    count, width, height = renderer._configured_geometry()
    assert (width, height, count) == (32, 8, 256)


def test_open_mmap_creates_world_writable_file(mmap_file):
    """The renderer seeds the mmap from config and makes it 0666 for demos."""
    renderer = rr.LedRenderer({'led_layout': 'single-24x8', 'led_count': 192})
    renderer.open_mmap()
    try:
        assert os.path.exists(mmap_file)
        mode = os.stat(mmap_file).st_mode & 0o777
        assert mode == 0o666
        magic, width, height, count = rr.parse_header(renderer._mmap)
        assert magic == rr.MMAP_MAGIC
        assert (width, height, count) == (WIDTH, HEIGHT, COUNT)
    finally:
        renderer._close_mmap()
