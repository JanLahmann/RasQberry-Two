#!/usr/bin/env python3
"""Parametric rebuild of the wall screw and nut (R2_Screw, R2_Hex_Nut).

Rebuilds `3D Model/originals/wall/R2_Screw.stl` and `R2_Hex_Nut.stl`
(SketchUp): a hollow screw with a hex head and its nut, e.g. for a cable
feed-through.

The thread is SketchUp's simple kind: a circle set off-centre from the axis
(`thread_ecc`) that turns once per `pitch` while it rises. The nut's bore is
the same shape, `nut_clearance` wider all round. Both turn the same way, so
the nut screws on.

Screw: hex head (31.7 across flats) 0..2 mm, hex collar (27.7) 2..5 mm,
thread 5..13 mm, Ø 20 bore all through.
Nut: hex 32.1 across flats, 3 mm high, with two round grip ridges on top.

Coordinates: axis on x = y = 0, standing on z = 0; hex corners on +-x.

Usage:  python screw_nut.py [--outdir ROOT] [--clearance MM]
"""
import argparse
import math
import sys
from pathlib import Path

from build123d import (Box, Circle, Cylinder, Plane, Pos, RegularPolygon, Rot,
                       extrude, loft)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PARAMS = dict(
    # thread (shared by screw and nut)
    thread_r=12.32,              # radius of the off-centre circle (screw)
    thread_ecc=0.53,             # its distance from the axis
    pitch=2.0,                   # rise per turn (right-hand)
    sections_per_turn=24,
    # angle of the circle's offset where each thread starts (only matters
    # for comparing with the original)
    screw_phase=168.6, nut_phase=89.4,
    # screw
    head_flats=31.71, head_h=2.0,
    collar_flats=27.71, collar_h=3.0,
    thread_len=8.0,
    bore_d=20.0,
    # nut
    nut_flats=32.08, nut_h=3.0,
    nut_clearance=0.355,         # bore radius minus thread radius
    # grip ridges on the nut's top: (x centre, chord width, height), 2 mm wide
    ridges=((15.745, 3.92, 1.5), (-15.72, 4.92, 2.0)), ridge_w=2.0,
)


def hex_prism(flats, z0, h):
    """Hexagon with corners on +-x, `flats` across the flats."""
    r = flats / math.sqrt(3)
    return extrude(Plane.XY.offset(z0) * RegularPolygon(r, 6), h)


def thread(p, r, z0, z1, phase0=0.0):
    """Off-centre circle of radius r turning once per pitch from z0 to z1."""
    n = max(2, round((z1 - z0) / p["pitch"] * p["sections_per_turn"]))
    secs = []
    for i in range(n + 1):
        z = z0 + (z1 - z0) * i / n
        a = phase0 + 2 * math.pi * (z - z0) / p["pitch"]
        e = p["thread_ecc"]
        secs.append(Plane.XY.offset(z) * Pos(e * math.cos(a), e * math.sin(a)) * Circle(r))
    return loft(secs)


def screw(p=PARAMS):
    z_thread = p["head_h"] + p["collar_h"]
    body = hex_prism(p["head_flats"], 0.0, p["head_h"])
    body += hex_prism(p["collar_flats"], p["head_h"] - 0.01, p["collar_h"] + 0.01)
    body += thread(p, p["thread_r"], z_thread - 0.01, z_thread + p["thread_len"],
                   math.radians(p["screw_phase"]))
    top = z_thread + p["thread_len"]
    body -= Pos(0, 0, top / 2) * Cylinder(p["bore_d"] / 2, top + 1)
    return body.clean()


def nut(p=PARAMS):
    h = p["nut_h"]
    body = hex_prism(p["nut_flats"], 0.0, h)
    for xc, chord, rise in p["ridges"]:
        rad = (chord ** 2 / 4 + rise ** 2) / (2 * rise)     # arc through the chord ends
        arc = Pos(xc, 0, h + rise - rad) * Rot(90, 0, 0) * Cylinder(rad, p["ridge_w"])
        body += arc & Pos(xc, 0, h + rise / 2) * Box(chord, p["ridge_w"], rise)
    r = p["thread_r"] + p["nut_clearance"]
    body -= thread(p, r, -0.5, h + 0.5, math.radians(p["nut_phase"]))
    return body.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--clearance", type=float, help="nut clearance in mm (default 0.355)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    p = dict(PARAMS)
    if a.clearance is not None:
        p["nut_clearance"] = a.clearance
    fmts = tuple(a.formats.split(","))
    for name, build in (("R2_Screw", screw), ("R2_Hex_Nut", nut)):
        part = build(p)
        vol = check_solid(part, name)
        print("%s: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (name, *bbox_size(part), vol))
        export_part(part, name, root=a.outdir, formats=fmts)


if __name__ == "__main__":
    main()
