#!/usr/bin/env python3
"""Parametric rebuild of the cryostat door (R2_NewDoor).

Rebuilds `3D Model/originals/cryostat/R2_NewDoor.stl` (SketchUp): the door
that closes the open face of the cryostat body.

Shape:
- a front panel 38.1 mm wide, 2.4 mm thick and 93.3 mm high (the module
  height). Its sides are bevelled at 60 deg (the faces of the hexagonal
  cryostat). The top 2 mm is a thinner lip (1.2 mm).
- the front face has a 0.3 mm recessed field between two V-grooves (the
  lower one also runs round the bevels), as on the RTE servers.
- two rails behind the panel, rounded at the top, each with two blind pin
  holes from the outside. These are the hinge and latch pins.
- a 3 mm foot that reaches under the cryostat. Its sides continue the 60 deg
  bevel.

Coordinates: front face on y = 0 (the foot points to +y), x = 0..38.1,
standing on z = 0.

Usage:  python new_door.py [--outdir ROOT]
"""
import argparse
import sys
from pathlib import Path

from build123d import Cylinder, Plane, Polygon, Pos, Rot, extrude, loft

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rqb_params  # noqa: E402
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PARAMS = dict(
    width=rqb_params.RTE_WIDTH, height=rqb_params.BODY_HEIGHT,
    panel=2.4,                   # panel thickness
    bevel_x=1.386,               # 60 deg side bevel over the panel thickness
    lip_z=91.3, lip=1.2,         # thinner lip at the top
    # rails behind the panel: outer x (from each side), width, depth, height
    rail_x=1.386, rail_w=3.0, rail_d=5.0, rail_z=(3.0, 84.8), rail_round=5.0,
    # blind pin holes from the outer face of each rail
    pin_r=1.6, pin_depth=2.2, pin_y=4.9, pin_z=(9.8, 74.8),
    # foot: 3 mm plate, trapezoid; sides at 60 deg from (bevel_x, foot_y0)
    foot_h=3.0, foot_y0=3.747, foot_depth=20.4, foot_top=(11.0, 27.1),
    # front: two grooves, 1 mm high (centre z, depth, how far the groove
    # bottom's corners move in from the panel edge), and a recessed field
    grooves=((2.5, 0.5, 0.5), (85.3, 0.66, 0.381)), groove_h=1.0,
    field_x=(2.0, 36.1), field_z=(5.0, 82.8), field_depth=0.3,
)


def prism(pts, z0, z1):
    return extrude(Plane.XY.offset(z0) * Polygon(*pts, align=None), z1 - z0, dir=(0, 0, 1))


def panel_profile(p, front=0.0, corner=0.0):
    """Panel cross-section; `front`/`corner` move the front face and its two
    corners inwards (the bottom of a V-groove)."""
    w, t, b = p["width"], p["panel"], p["bevel_x"]
    return [(corner, front), (w - corner, front), (w - b, t), (b, t)]


def groove(p, zc, depth, corner):
    """V-groove across the front, centred at zc; `corner` > the bevel's own
    inset at that depth carries it round the bevels too."""
    g = p["groove_h"] / 2
    full = panel_profile(p)
    inner = panel_profile(p, front=depth, corner=corner)
    slab = prism(full, zc - g, zc + g)
    lo = Plane.XY.offset(zc - g) * Polygon(*full, align=None)
    mid = Plane.XY.offset(zc) * Polygon(*inner, align=None)
    hi = Plane.XY.offset(zc + g) * Polygon(*full, align=None)
    return slab - (loft([lo, mid]) + loft([mid, hi]))


def rail(p, x0):
    """One rail, x0..x0 + rail_w, rounded at the top (quarter circle on the
    panel's back face)."""
    t, d, r = p["panel"], p["rail_d"], p["rail_round"]
    z0, z1 = p["rail_z"]
    w = p["rail_w"]
    foot = [(x0, t), (x0 + w, t), (x0 + w, t + d), (x0, t + d)]
    body = prism(foot, z0, z1 - r)
    round_top = Pos(x0 + w / 2, t, z1 - r) * Rot(0, 90, 0) * Cylinder(r, w)
    return body + (round_top & prism(foot, z1 - r - 0.01, z1))


def build(p=PARAMS):
    w, h, t = p["width"], p["height"], p["panel"]
    door = prism(panel_profile(p), 0.0, p["lip_z"])
    lip = [(0, 0), (w, 0), (w - p["bevel_x"] * p["lip"] / t, p["lip"]),
           (p["bevel_x"] * p["lip"] / t, p["lip"])]
    door += prism(lip, p["lip_z"] - 0.01, h)
    b, y0, fd = p["bevel_x"], p["foot_y0"], p["foot_depth"]
    fx0, fx1 = p["foot_top"]
    door += prism([(0, 0), (w, 0), (w - b, t), (w - b, y0), (fx1, fd), (fx0, fd),
                   (b, y0), (b, t)], 0.0, p["foot_h"])
    x_left = p["rail_x"]
    x_right = w - p["rail_x"] - p["rail_w"]
    for x0 in (x_left, x_right):
        door += rail(p, x0)
    # pin holes, blind from the outer face of each rail
    for z in p["pin_z"]:
        for x_out, sign in ((x_left, +1), (x_right + p["rail_w"], -1)):
            xc = x_out + sign * (p["pin_depth"] - 0.01) / 2
            door -= Pos(xc, p["pin_y"], z) * Rot(0, 90, 0) * Cylinder(p["pin_r"], p["pin_depth"] + 0.01)
    for zc, depth, corner in p["grooves"]:
        door -= groove(p, zc, depth, corner)
    (fx_0, fx_1), (fz0, fz1) = p["field_x"], p["field_z"]
    door -= prism([(fx_0, -0.01), (fx_1, -0.01), (fx_1, p["field_depth"]),
                   (fx_0, p["field_depth"])], fz0, fz1)
    return door.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    part = build()
    vol = check_solid(part, "NewDoor")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "R2_NewDoor", root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
