#!/usr/bin/env python3
"""
Fixes from the fresh-card user tests of 2026-10-07 (demo side).

Run with:
    python3 -m pytest tests/unit/ -q
"""

import json
import os
import struct
import sys
import types

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_REPO_ROOT, "RQB2-bin")
sys.path.insert(0, _BIN)

import rq_led_utils as lu  # noqa: E402


def _read(name):
    with open(os.path.join(_BIN, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. The on-screen LED view during the LED panel check
# ---------------------------------------------------------------------------

def test_view_undoes_the_writer_brightness():
    """The check's white IBM at 15 % (38, 38, 38) was darker than the view's
    'off' grey (Pi 5 P3): the view shows it at full colour now."""
    assert lu.view_rgb(38, 38, 38, 38) == (255, 255, 255)
    assert lu.view_rgb(0, 0, 38, 38) == (0, 0, 255)
    assert lu.view_rgb(10, 20, 30, 0) == (10, 20, 30)       # not recorded: as is
    assert lu.view_rgb(10, 20, 30, 255) == (10, 20, 30)


def test_writer_records_its_brightness_in_the_header(tmp_path, monkeypatch):
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(tmp_path / "bus"))
    from rq_led_virtual import VirtualNeoPixel
    px = VirtualNeoPixel(None, 4, brightness=0.15, width=4, height=1)
    raw = (tmp_path / "bus").read_bytes()
    assert raw[:4] == b"RQL1"
    assert struct.unpack("<HHH", raw[4:10]) == (4, 1, 4)
    assert raw[10] == 38
    px.brightness = 0.4
    assert (tmp_path / "bus").read_bytes()[10] == 102
    px.deinit()


@pytest.fixture
def hint(tmp_path, monkeypatch):
    path = tmp_path / "view-layout.json"
    monkeypatch.setattr(lu, "VIEW_LAYOUT_HINT", str(path))
    monkeypatch.setattr(lu, "get_led_config", lambda: {"led_layout": "single-24x8"})
    return path


def test_view_follows_the_layout_the_check_draws_in(hint):
    assert lu.view_layout() == ("single-24x8", "single-24x8")
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    assert lu.view_layout() == ("quad-4x12", "quad-4x12")
    lu.clear_view_layout_hint()
    assert lu.view_layout() == ("single-24x8", "single-24x8")


def test_a_hint_from_a_check_that_died_does_not_count(hint):
    hint.write_text(json.dumps({"pid": 2 ** 22 + 12345, "layout": "quad-4x12",
                                "label": "quad-4x12"}))
    assert lu.view_layout() == ("single-24x8", "single-24x8")
    hint.write_text("not json")
    assert lu.view_layout() == ("single-24x8", "single-24x8")


def test_probe_names_its_layout_only_for_the_check(hint, monkeypatch):
    import rq_led_wizard_probe as probe
    monkeypatch.delenv("RQ_LED_VIEW_OWNER", raising=False)
    probe.tell_views("logo", "quad-4x12")
    assert not hint.exists()                         # demos never write it

    monkeypatch.setenv("RQ_LED_VIEW_OWNER", str(os.getpid()))
    probe.tell_views("logo", "quad-4x12")
    assert lu.view_layout() == ("quad-4x12", "quad-4x12")

    probe.tell_views("logo", "single-24x8", toggle_y=True)
    layout, label = lu.view_layout()
    assert label == "single-24x8, upside down"
    assert layout["y_flip"] != lu.get_layout("single-24x8").get("y_flip", False)

    probe.tell_views("clear", None)                  # raw chain order again
    assert not hint.exists()


def test_the_check_names_itself_for_the_probes():
    src = _read("rq_led_setup_wizard.sh")
    assert 'export RQ_LED_VIEW_OWNER="$$"' in src


def test_window_title_follows_the_layout(hint):
    pytest.importorskip("tkinter")
    import rq_led_virtual_gui as gui
    titles = []
    fake = types.SimpleNamespace(
        width=24, height=8, layout="single-24x8", label="single-24x8",
        _last_frame=(b"x", 38), root=types.SimpleNamespace(title=titles.append))
    fake._set_title = lambda: gui.VirtualLEDMatrix._set_title(fake)
    assert gui.VirtualLEDMatrix.follow_layout(fake) is False
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    assert gui.VirtualLEDMatrix.follow_layout(fake) is True
    assert titles[-1] == "RasQberry Virtual LED Matrix - 24x8 (quad-4x12)"
    assert fake._last_frame is None                  # redrawn in the new map


def test_web_view_shows_the_check_layout_and_undoes_brightness(tmp_path, monkeypatch, hint):
    import rq_led_web as web
    bus = tmp_path / "bus"
    count = 192
    pixels = bytearray(count * 3)
    idx = lu.map_xy_to_pixel(0, 0, layout="quad-4x12")
    pixels[idx * 3:idx * 3 + 3] = bytes((38, 38, 38))
    bus.write_bytes(b"RQL1" + struct.pack("<HHHB", 24, 8, count, 38) + b"\x00" * 5
                    + b"\x01" + bytes(pixels))
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(bus))
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    frame = web.read_frame()
    assert frame["layout"] == "quad-4x12"
    assert frame["rows"][0][0] == [255, 255, 255]
