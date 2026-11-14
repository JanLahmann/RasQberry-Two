#!/usr/bin/env python3
"""Plugs that hold the cryostat and the wall on the floor without screw and
nut (they replace R2_Screw + R2_Hex_Nut and the ScrewOctopus).

The openings are already there and stay unchanged, so floor, cryostat and
wall still stand on a table:
- floor hole where Tile1-4 meet = the cryostat's bottom opening: a hexagon
  (27.9 mm across the flats, 32.2 across the corners) with three slots;
- the two floor holes under the wall = the wall base's bolt holes: the same
  hexagon without slots.

`R2_Floor-CryoPlug` (print once): that opening's shape, `clearance`
smaller, with a thin flange under the floor plate. It fills the floor hole
and goes up through the cryostat's 3 mm floor (0.2 mm beyond it), so the
cryostat cannot
slide or turn and lifts straight off.

`R2_Floor-WallPlug` (print twice), a bayonet: a winged flange under the
floor plate, a round core through the floor plate and the wall's floor (it
turns in the hexagon), and on top the hexagon itself, `clearance` smaller.
Push it up with the hexagon lined up and turn it 30 deg by the wings: the
hexagon's corners now lie over the flats and clamp the wall's floor and the
floor plate against the wings. Turn back to take the wall off.

Both keep the Ø 20 bore of the hollow screw for cables. Values from test
prints (Jan, Nov 2026): clearance 0.05 mm; cryostat plug 6.2 mm above its
flange; wall plug 6.2 mm between wings and hexagon (6.0-5.8 was too tight).

The `...Test` prints add 3 mm plates with the holes to try the fit on
another printer. The outlines are measured from the rebuilt parts in
print/ (Floor-all, NarrowYCryoConjoined, Wall-Base; under --outdir when
given), so build those first.

Usage:  python plugs.py [--outdir ROOT] [--only CryoPlug,WallPlug,...]
"""
import argparse
import functools
import math
import sys
from pathlib import Path

import shapely.affinity as sa
import shapely.geometry as sg
import trimesh
from build123d import Cylinder, Pos

CAD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAD))
import rqb_params  # noqa: E402
from rqb_cad import OUTPUT, bbox_size, check_solid, export_part, part_path  # noqa: E402
from floor_model import prism, top_chamfer  # noqa: E402

PARAMS = dict(
    clearance=0.05,      # plug outline inside the tightest opening
    bore_d=rqb_params.CABLE_BORE_D,
    test_plate=3.0,
    # cryostat plug
    cryo_flange=2.0, cryo_rim=4.0,   # flange under the floor plate, rim beyond the hole
    cryo_shaft=6.2,      # above the flange: floor plate 3 + 3.2 into the cryostat
    cryo_lead_in=0.6,
    # wall plug
    core_play=0.1,       # round core inside the hexagon's flats (it turns)
    grip=6.2,            # wings to hexagon: floor plate 3 + wall floor 3, plus play
    # wings: 4 mm of the 7 mm space under the floor plate; the nearest
    # skirt is 34.4 mm from the wall holes
    flange=4.0, wing_span=50.0, wing_w=12.0, hub_wall=6.0,
    lug=2.0,             # height of the hexagon on top
    lead_in=0.4,
)
# (part in rqb_cad.PARTS, z of a section through the hole, the hole's
# centre): the plugs are built round the origin, so the centre must be exact
# (hole() checks it against the outline's centroid)
HOLES = dict(
    floor_cryo=("R2_Floor-all", 8.5, (130.32, 140.18)),
    cryo=("R2_NarrowYCryoConjoined", 1.5, (0.0, 10.25)),
    wall=("R2_Wall-Base", 1.5, (30.20, 27.27)),
    floor_wall=("R2_Floor-all", 8.5, (37.36, 322.27)),
)
HOLE_MAX_AREA = 2000.0   # mm2: larger loops are outlines of the part, not the hole
CENTRE_TOL = 0.05


@functools.cache
def load(root, name):
    """Mesh of built part `name`, back in unscaled mm (the STLs in print/
    have rqb_params.SCALE applied, and export_part applies it to the plugs)."""
    m = trimesh.load(f"{part_path(name, root=root)}.stl", force="mesh")
    return m.apply_scale(1 / rqb_params.SCALE)


def hole(spec, root=OUTPUT):
    """The hole of the part's section at z that contains point `pt`,
    moved so that `pt` is the origin. Parts are read from `root`."""
    name, z, pt = spec
    for loop in load(root, name).section([0, 0, 1], [0, 0, z]).discrete:
        p = sg.Polygon(loop[:, :2])
        if p.contains(sg.Point(pt)) and p.area < HOLE_MAX_AREA:
            if p.centroid.distance(sg.Point(pt)) > CENTRE_TOL:
                raise ValueError(f"{name}: hole centre is {p.centroid}, not {pt}")
            return sa.translate(p.buffer(0), -pt[0], -pt[1])
    raise ValueError(f"{name}: no hole at {pt}")


class Holes(dict):
    """HOLES measured on first use, so a plug needs only its own parts."""

    def __init__(self, root):
        super().__init__()
        self.root = root

    def __missing__(self, key):
        self[key] = hole(HOLES[key], self.root)
        return self[key]


def bored(body, top, prm):
    """`body` with the cable bore all through (z 0..top; 0.5 mm beyond both
    ends so no faces coincide)."""
    return (body - Pos(0, 0, top / 2) * Cylinder(prm["bore_d"] / 2, top + 1)).clean()


def cryo_plug(holes, prm=PARAMS):
    """Flange (z 0..cryo_flange), then the opening's outline up through the
    floor plate into the cryostat; chamfered top."""
    outline = (holes["floor_cryo"].intersection(holes["cryo"])
               .buffer(-prm["clearance"], join_style=2).simplify(0.01))
    f, h = prm["cryo_flange"], prm["cryo_shaft"]
    shaft = top_chamfer(prism(outline, -h, 0.0), prm["cryo_lead_in"])
    body = prism(outline.buffer(prm["cryo_rim"]), 0.0, f + 0.01) + Pos(0, 0, f + h) * shaft
    return bored(body, f + h, prm)


def shared_hexagon(holes, clearance):
    """The hexagon all four openings share (the cryostat's slots drop out),
    `clearance` inside the tightest one, as a regular hexagon: the measured
    outline has short facets that the lead-in chamfer cannot follow. The
    tightest is the floor's cryostat hole, as in the tested plugs; the wall
    holes get about 0.13 mm."""
    common = functools.reduce(sg.Polygon.intersection, (holes[k] for k in HOLES))
    r = (sg.Point(0, 0).distance(common.exterior) - clearance) / math.cos(math.pi / 6)
    hexagon = sg.Polygon([(r * math.cos(k * math.pi / 3), r * math.sin(k * math.pi / 3))
                          for k in range(6)])
    if not common.contains(hexagon):
        raise ValueError("wall plug: hexagon does not fit the openings")
    return hexagon


def wings(prm=PARAMS):
    """Flange outline: a hub round the bore with two ears, like a wing nut."""
    h = (prm["wing_span"] - prm["wing_w"]) / 2
    ears = sg.LineString([(-h, 0), (h, 0)]).buffer(prm["wing_w"] / 2, 32)
    return ears.union(sg.Point(0, 0).buffer(prm["bore_d"] / 2 + prm["hub_wall"], 64))


def wall_plug(holes, prm=PARAMS):
    """Wings z 0..flange, core through the grip, hexagon on top."""
    hexagon = shared_hexagon(holes, prm["clearance"])
    f, g, t = prm["flange"], prm["grip"], prm["lug"]
    core_r = sg.Point(0, 0).distance(hexagon.exterior) - prm["core_play"]
    top = f + g + t
    head = Pos(0, 0, top) * top_chamfer(prism(hexagon, -t, 0.0), prm["lead_in"])
    body = (prism(wings(prm), 0.0, f)
            + Pos(0, 0, f + g / 2) * Cylinder(core_r, g + 0.02) + head)
    return bored(body, top, prm)


def with_plates(plug, plates, prm=PARAMS):
    """`plug` and test plates [(hole outline, size, (x, y))], as separate pieces."""
    out = plug
    for outline, size, (x, y) in plates:
        sq = sg.box(-size / 2, -size / 2, size / 2, size / 2).difference(outline)
        out += Pos(x, y, 0) * prism(sq, 0.0, prm["test_plate"])
    out = out.clean()
    if len(out.solids()) != 1 + len(plates):
        raise ValueError(f"plug test: {len(out.solids())} pieces")
    return out


def main():
    """Build the plugs named in --only from the parts under --outdir (or print/)."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--only", default="CryoPlug,CryoPlugTest,WallPlug,WallPlugTest")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    holes = Holes(a.outdir or OUTPUT)
    cryo = functools.cache(lambda: cryo_plug(holes))
    wall = functools.cache(lambda: wall_plug(holes))
    builds = {
        "CryoPlug": cryo,
        "CryoPlugTest": lambda: with_plates(cryo(), [(holes["floor_cryo"], 60, (0, 60)),
                                                   (holes["cryo"], 50, (0, -55))]),
        "WallPlug": wall,
        "WallPlugTest": lambda: with_plates(wall(), [(holes["floor_wall"], 40, (0, 50)),
                                                   (holes["wall"], 40, (50, 50))]),
    }
    for key in a.only.split(","):
        name = f"R2_Floor-{key}"
        part = builds[key]()
        for i, s in enumerate(part.solids()):
            check_solid(s, f"{name} piece {i}")
        print("%s: size %.2f x %.2f x %.2f mm" % (name, *bbox_size(part)))
        export_part(part, name, root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
