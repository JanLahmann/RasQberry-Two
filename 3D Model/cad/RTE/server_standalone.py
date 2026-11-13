#!/usr/bin/env python3
"""Parametric rebuild of the standalone double server (R2_ServerStandalone).

Rebuilds `3D Model/originals/cryostat/Standalone Version/
R2_ServerStandalone.stl` (SketchUp): two original narrow servers
(narrow_server.py, variant "original") standing front to front, 0.2 mm
apart, with the two front walls cut away over the cavity width, so they
share one cavity (38.1 x 46.7 mm footprint). The cups are on the two outer
(back) walls. A 0.2 mm filler joins the two side walls and the floors; the
V notch where the chamfered corners meet stays, as in the original.

Coordinates: centred on x = y = 0, standing on z = 0, the servers' long side
along x (the original stands rotated by 30 deg next to the cryostat; the
print file is axis-aligned).

Usage:  python server_standalone.py [--outdir ROOT]
"""
import argparse
import sys
from pathlib import Path

from build123d import Pos, Rot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402
from narrow_server import _box, build, variant  # noqa: E402

PARAMS = dict(
    gap=0.2,             # between the two front faces
    filler_x=18.3,       # the filler reaches to here (outer face 19.05 minus the chamfer notch)
)


def build_pair(p=PARAMS, open_end=False):
    """The pair, centred. open_end=True: the -y server has no cups and its
    back wall is cut away over the cavity width too (an arm of
    ../cryostat/narrow_y_conjoined.py, open towards the cryostat)."""
    s = variant("original")
    s["open_front"] = True
    one = build(s)
    off = s["depth"] / 2 + p["gap"] / 2
    if open_end:
        e = dict(s, mount_walls=(), cup_pocket=None)
        end = build(e)
        hy, cx = e["depth"] / 2, e["cavity_x"]
        end -= _box(cx[0], cx[1], e["cavity_y"][1] - 0.01, hy + 1, e["floor"], e["height"] + 1)
        a = Pos(0, -off, 0) * Rot(0, 0, 180) * end
    else:
        a = Pos(0, -off, 0) * Rot(0, 0, 180) * one   # back wall (cups) at -y
    b = Pos(0, off, 0) * one       # back wall (cups) at +y
    g, fx, H, fl = p["gap"] / 2 + 0.01, p["filler_x"], s["height"], s["floor"]
    cx = s["cavity_x"]
    filler = _box(-fx, fx, -g, g, 0, H) - _box(cx[0], cx[1], -g - 1, g + 1, fl, H + 1)
    return (a + b + filler).clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    part = build_pair()
    vol = check_solid(part, "ServerStandalone")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "R2_ServerStandalone", root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
