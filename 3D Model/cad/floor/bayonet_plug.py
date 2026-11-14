#!/usr/bin/env python3
"""Bayonet plug: holds the cryostat and the wall on the floor without
screw and nut (replaces R2_Screw + R2_Hex_Nut and the ScrewOctopus).

The openings are already there and stay unchanged:
- floor hole where Tile1-4 meet = the cryostat's bottom opening: a hexagon
  (27.9 mm across the flats, 32.2 across the corners) with three slots;
- the two floor holes under the wall = the wall base's bolt holes: the same
  hexagon.

The plug: a winged flange under the floor plate, a round core through the
floor plate and the part's floor (it turns in the hexagon), and on top the
hexagon itself, `clearance` smaller. Push it up through floor and part with
the hexagon aligned and turn it by 30 deg at the wings: the hexagon's
corners now lie over the flats of the part's opening and clamp floor and
part between them and the flange. Turn back to lift the part off; the part
still stands on a table. The Ø 20 bore keeps the cable passage. One plug
fits all three places (both floors are 3 mm): print it three times.

Values from test prints (Jan, Nov 2026): clearance 0.05 mm, grip 6.2 mm
(6.0-5.8 was too tight), wings rather than a round flange.

`R2_Floor-BayonetTest` is the plug with three 3 mm plates to try the fit
on another printer: the floor's cryostat hole (60 mm), the cryostat's
opening (50 mm) and the wall's hex hole (40 mm).

The outlines are measured from the rebuilt parts in print/ (Floor-all,
NarrowYCryoConjoined, Wall-Base), so build those first.

Usage:  python bayonet_plug.py [--outdir ROOT] [--only Plug,Test]
"""
import argparse
import math
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
    clearance=0.05,      # hexagon inside the tightest opening
    core_play=0.1,       # round core inside the hexagon's flats (it turns)
    grip=6.2,            # flange to hexagon: floor plate 3 + part floor 3, plus play
    # winged flange: 4 mm of the 7 mm space under the floor plate; the
    # nearest skirt is 26.9 mm from the cryostat hole, 34.4 from the wall's
    flange=4.0, wing_span=50.0, wing_w=12.0, hub_wall=6.0,
    lug=2.0,             # height of the hexagon on top
    lead_in=0.4,         # chamfer on top
    bore_d=20.0,
    test_plate=3.0,
)
# (stl in print/, z of a section through the hole, a point inside the hole)
HOLES = dict(
    floor_cryo=("floor/R2_Floor-all.stl", 8.5, (130.32, 140.18)),
    cryo=("cryostat/R2_NarrowYCryoConjoined.stl", 1.5, (0.0, 10.25)),
    wall=("wall/R2_Wall-Base.stl", 1.5, (30.20, 27.27)),
    floor_wall=("floor/R2_Floor-all.stl", 8.5, (37.36, 322.27)),
)


def hole(spec):
    """The hole of the part's section at z that contains point `pt`,
    moved so that `pt` is the origin."""
    path, z, pt = spec
    m = trimesh.load(OUTPUT / path, force="mesh")
    for loop in m.section([0, 0, 1], [0, 0, z]).discrete:
        p = sg.Polygon(loop[:, :2])
        if p.contains(sg.Point(pt)) and p.area < 2000:
            return sa.translate(p.buffer(0), -pt[0], -pt[1])
    raise ValueError(f"{path}: no hole at {pt}")


def shared_hexagon(holes, clearance):
    """The hexagon all four openings share (the cryostat's slots drop out),
    `clearance` inside the tightest one, as a regular hexagon: the measured
    outline has short facets that the lead-in chamfer cannot follow."""
    common = holes["cryo"]
    for h in holes.values():
        common = common.intersection(h)
    r = (sg.Point(0, 0).distance(common.exterior) - clearance) / math.cos(math.pi / 6)
    hexagon = sg.Polygon([(r * math.cos(k * math.pi / 3), r * math.sin(k * math.pi / 3))
                          for k in range(6)])
    if not common.contains(hexagon):
        raise ValueError("bayonet plug: hexagon does not fit the openings")
    return hexagon


def wings(prm=PARAMS):
    """Flange outline: a hub round the bore with two ears, like a wing nut."""
    h = (prm["wing_span"] - prm["wing_w"]) / 2
    ears = sg.LineString([(-h, 0), (h, 0)]).buffer(prm["wing_w"] / 2, 32)
    return ears.union(sg.Point(0, 0).buffer(prm["bore_d"] / 2 + prm["hub_wall"], 64))


def plug(hexagon, prm=PARAMS):
    """Flange z 0..flange, core through the grip, hexagon on top."""
    f, g, t = prm["flange"], prm["grip"], prm["lug"]
    core_r = sg.Point(0, 0).distance(hexagon.exterior) - prm["core_play"]
    top = f + g + t
    head = Pos(0, 0, top) * top_chamfer(prism(hexagon, -t, 0.0), prm["lead_in"])
    body = (prism(wings(prm), 0.0, f)
            + Pos(0, 0, f + g / 2) * Cylinder(core_r, g + 0.02) + head)
    return (body - Pos(0, 0, top / 2) * Cylinder(prm["bore_d"] / 2, top + 1)).clean()


def test_plate(outline, size, prm=PARAMS):
    return prism(sg.box(-size / 2, -size / 2, size / 2, size / 2).difference(outline),
                 0.0, prm["test_plate"])


def bayonet_test(p, holes, prm=PARAMS):
    """The plug `p` with the floor, cryostat and wall test plates."""
    out = p
    for piece in (Pos(0, 60, 0) * test_plate(holes["floor_cryo"], 60, prm),
                  Pos(60, 60, 0) * test_plate(holes["cryo"], 50, prm),
                  Pos(60, 0, 0) * test_plate(holes["wall"], 40, prm)):
        out += piece
    out = out.clean()
    if len(out.solids()) != 4:
        raise ValueError(f"bayonet test: {len(out.solids())} pieces")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--only", default="Plug,Test", help="Plug and/or Test")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    holes = {k: hole(v) for k, v in HOLES.items()}
    p = plug(shared_hexagon(holes, PARAMS["clearance"]))
    builds = {"Plug": lambda: p, "Test": lambda: bayonet_test(p, holes)}
    for key in a.only.split(","):
        name = f"R2_Floor-Bayonet{key}"
        part = builds[key]()
        for i, s in enumerate(part.solids()):
            check_solid(s, f"{name} piece {i}")
        print("%s: size %.2f x %.2f x %.2f mm" % (name, *bbox_size(part)))
        export_part(part, name, root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
