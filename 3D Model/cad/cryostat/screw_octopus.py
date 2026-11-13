#!/usr/bin/env python3
"""Parametric rebuild of the octopus alignment screw (R2_ScrewOctopusAlignment2).

Rebuilds `3D Model/originals/cryostat/R2_ScrewOctopusAlignment2.stl`
(SketchUp, mesh only).

Shape, from the bottom:
- a hexagonal hub (31.7 mm across the flats, 4 mm high) with three arms
  at 120 deg, each 36 mm long from the hub's flat. An arm is a 4 mm strip,
  1 mm thick, with two 1 mm rails on top (2 mm higher). The rails lean
  outwards, so the arm is 4 mm wide at the bottom and 6 mm at the top.
- a smaller hexagon (16 mm side, 27.7 mm across the flats) up to z = 8.5;
- a threaded tube up to z = 15. The thread is drawn the way the SketchUp
  model has it: a circle of radius 12.28 mm, 0.70 mm off the axis, that
  turns once per 2 mm of height (one start, anticlockwise going up).
- a round hole (r 9.97 mm) through everything.

Coordinates: hub centred on x = y = 0 (the original sits at x -39.96,
y -6.31), first arm along +y, standing on z = 0.

Usage:  python screw_octopus.py [--outdir ROOT]
"""
import argparse
import math
import sys
from pathlib import Path

from build123d import (
    Circle, Plane, Polygon, Pos, Rot, RegularPolygon, extrude, loft,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PARAMS = dict(
    hub_flat=31.722, hub_h=4.0,          # base hexagon: across the flats, height
    hex2_side=16.0, hex2_top=8.5,        # upper hexagon: side (= circumradius), top
    arm_end=51.861,                      # arm tip, from the hub centre
    arm_angles=(90.0, 210.0, 330.0),     # arm directions (deg); hub flats face them
    # arm cross-section, half profile (x across the arm, z): bottom 4 mm,
    # 1 mm strip, rails 1 mm wide, leaning out (outer edge (2,0)->(3,2))
    arm_half=((0.0, 0.0), (2.0, 0.0), (3.0, 2.0), (3.0, 4.0), (2.0, 4.0),
              (2.0, 2.0), (1.5, 1.0), (0.0, 1.0)),
    # thread: eccentric circle, one turn per pitch, anticlockwise upwards
    thread_r=12.281, thread_ecc=0.702, pitch=2.0, top=15.0,
    thread_phase=-174.3,                 # direction of the offset at z = hex2_top (deg)
    sections_per_turn=24,
    hole_r=9.97,
)


def arm(p, angle):
    """One arm along +y from inside the hub to arm_end, turned to `angle`."""
    half = list(p["arm_half"])
    pts = [(-x, z) for x, z in reversed(half)] + half[1:-1]
    start = p["hub_flat"] / 2 - 1.0      # starts inside the hub
    plane = Plane(origin=(0, start, 0), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))  # local y = up
    body = extrude(plane * Polygon(*pts, align=None), p["arm_end"] - start)
    return Rot(0, 0, angle - 90.0) * body


def thread(p):
    """The eccentric-circle thread from hex2_top to top, lofted through
    sections_per_turn circles per turn."""
    z0, z1 = p["hex2_top"], p["top"]
    n = math.ceil((z1 - z0) / p["pitch"] * p["sections_per_turn"])
    secs = []
    for i in range(n + 1):
        z = z0 + (z1 - z0) * i / n
        a = math.radians(p["thread_phase"] + 360.0 * (z - z0) / p["pitch"])
        e = p["thread_ecc"]
        secs.append(Plane.XY.offset(z) * Pos(e * math.cos(a), e * math.sin(a)) * Circle(p["thread_r"]))
    return loft(secs)


def build(p=PARAMS):
    hub_r = p["hub_flat"] / math.sqrt(3)          # circumradius
    # RegularPolygon puts a corner on +x: flats then face 90/210/330 deg
    part = extrude(RegularPolygon(hub_r, 6), p["hub_h"])
    part += extrude(Plane.XY.offset(p["hub_h"] - 0.01) * RegularPolygon(p["hex2_side"], 6),
                    p["hex2_top"] - p["hub_h"] + 0.01)
    for a in p["arm_angles"]:
        part += arm(p, a)
    part += thread(p)
    part -= Pos(0, 0, -1) * extrude(Circle(p["hole_r"]), p["top"] + 2)
    return part.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    part = build()
    vol = check_solid(part, "ScrewOctopusAlignment2")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "R2_ScrewOctopusAlignment2", root=a.outdir,
                formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
