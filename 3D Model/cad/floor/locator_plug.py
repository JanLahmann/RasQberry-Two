#!/usr/bin/env python3
"""Locator plug: puts the cryostat (and later the wall) on the floor
without screw and nut.

The cryostat's bottom opening and the floor hole where Tile1-4 meet have
the same shape (a hex with three tabs) at the same place. The plug is that
shape, `clearance` smaller all round: it sits in the floor hole with a
flange under the plate and sticks `engage` mm up into the cryostat's
opening, so the cryostat cannot slide or turn but lifts straight off.
Floor and cryostat stay unchanged (the cryostat still stands on a table).
The Ø 20 bore keeps the cable passage of the hollow screw.

`PlugTest` is the test print: the plug plus two 3 mm plates, the floor's
hole in the larger one, the cryostat's opening in the smaller one.

The outlines are measured from the rebuilt parts in print/ (Floor-all,
NarrowYCryoConjoined), so run floor_model.py and cryostat first.

Usage:  python locator_plug.py [--outdir ROOT]
"""
import argparse
import sys
from pathlib import Path

import shapely.affinity as sa
import shapely.geometry as sg
import trimesh
from build123d import Cylinder, Pos

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import OUTPUT, bbox_size, check_solid, export_part  # noqa: E402
from floor_model import prism, top_chamfer  # noqa: E402

PARAMS = dict(
    clearance=0.05,      # plug outline inside the holes (from the joint tests)
    floor_plate=3.0,     # floor tile plate
    engage=2.5,          # up into the cryostat's 3 mm floor
    flange=2.0, flange_rim=4.0,   # under the floor plate, rim beyond the hole
    bore_d=20.0,
    lead_in=0.6,         # chamfer on the plug's top
    test_plate=3.0,
)
# where the opening is: Floor-all (plate z 7..10) and NarrowYCryoConjoined
# (floor z 0..3), both in their print frames
FLOOR_HOLE = ("floor/R2_Floor-all.stl", 8.5, (130.32, 140.18))
CRYO_HOLE = ("cryostat/R2_NarrowYCryoConjoined.stl", 1.5, (0.0, 10.25))


def hole(spec):
    """The hole of the part's section at z that contains point `pt`,
    moved so that `pt` is the origin."""
    path, z, pt = spec
    m = trimesh.load(OUTPUT / path, force="mesh")
    s = m.section([0, 0, 1], [0, 0, z])
    for loop in s.discrete:
        p = sg.Polygon(loop[:, :2])
        if p.contains(sg.Point(pt)) and p.area < 2000:
            return sa.translate(p.buffer(0), -pt[0], -pt[1])
    raise ValueError(f"{path}: no hole at {pt}")


def plug(outline, prm=PARAMS):
    """Flange under the floor plate (z 0..flange), then the outline through
    the plate and up into the part; chamfered top, bore all through."""
    f, h = prm["flange"], prm["floor_plate"] + prm["engage"]
    shaft = top_chamfer(prism(outline, -h, 0.0), prm["lead_in"])
    body = prism(outline.buffer(prm["flange_rim"]), 0.0, f + 0.01) + Pos(0, 0, f + h) * shaft
    top = f + h
    return (body - Pos(0, 0, top / 2) * Cylinder(prm["bore_d"] / 2, top + 1)).clean()


def test_plate(outline, size, prm=PARAMS):
    return prism(sg.box(-size / 2, -size / 2, size / 2, size / 2).difference(outline),
                 0.0, prm["test_plate"])


def plug_test(prm=PARAMS):
    floor, cryo = hole(FLOOR_HOLE), hole(CRYO_HOLE)
    outline = floor.intersection(cryo).buffer(-prm["clearance"], join_style=2).simplify(0.01)
    out = (plug(outline, prm) + Pos(0, 60, 0) * test_plate(floor, 60, prm)
           + Pos(0, -55, 0) * test_plate(cryo, 50, prm)).clean()
    if len(out.solids()) != 3:
        raise ValueError("plug test: pieces touch each other")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    part = plug_test()
    for i, s in enumerate(part.solids()):
        check_solid(s, f"PlugTest piece {i}")
    print("R2_Floor-PlugTest: size %.2f x %.2f x %.2f mm" % bbox_size(part))
    export_part(part, "R2_Floor-PlugTest", root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
