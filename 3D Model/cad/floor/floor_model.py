#!/usr/bin/env python3
"""Parametric rebuild of the floor tiles (R2_Floor-Tile1..6s, -Tile1Mag/2Mag, -all).

The floor is 260 x 390 mm in six 130 x 130 tiles (2 x 3), 10 mm high:

- a 3 mm top plate with a 0.75 mm 45 deg chamfer round its top edges, so
  neighbouring tiles meet in a small V;
- a 3 mm skirt underneath (z -10 .. -3) round the tile, open where cables
  or the server/cryostat feet need room;
- dovetail joints under the plate where two tiles meet (see joint());
  no pins or screws, and nothing shows on top;
- the tile number, mirrored, raised 2 mm under the plate;
- Tile5 / Tile6s (the front row): a V-groove cross on top dividing the tile
  into four 65 mm squares, a hexagonal hole, and a half of a Ø 22 cable
  hole on the edge they share; Tile6s also carries a small relief sign
  underneath;
- the "Mag" versions of Tile1/Tile2 have three Ø 16 x 1 mm pockets in the
  underside of the plate for magnets.

The outlines that are not simple numbers (plate, skirt, relief) are measured
from the originals by extract_floor.py into floor_profiles.json; the rest is
in PARAMS / TILES below. All tiles share the original's coordinate frame
(the whole floor: x 0..260, y 0..390, top at z = 0).

Usage:  python floor_model.py [--outdir ROOT] [--only Tile1,Tile5,...,all,JointTest]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import shapely.geometry as sg
from build123d import (Axis, Box, Cylinder, Face, Plane, Polygon, Pos, Rot, Wire, chamfer,
                       extrude)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PROFILES = json.loads(Path(__file__).with_name("floor_profiles.json").read_text())

PARAMS = dict(
    plate=3.0, height=10.0,      # plate thickness, total height (z -10 .. 0)
    top_chamfer=0.75,
    groove_depth=0.75,           # V-grooves on top (90 deg)
    wall=3.0,
    # dovetail joints (see joint()): neck and head width, length beyond
    # the seam, clearance all round in the socket, gap under the plate
    # above the tab, overhang of the tab's sloped top (deg from vertical,
    # as printed plate-down)
    tail_neck=7.0, tail_head=11.0, tail_len=5.5, tail_clearance=0.05,
    tail_gap=0.3, tail_overhang=45.0, socket_wall=2.5,
    magnet_d=15.93, magnet_depth=1.0,
    cable_hole_r=11.03,
)

# what is not in the measured outlines: grooves (x = ..., y = ...) and the
# cable hole centre. Mag tiles are their base tile plus the magnet pockets.
TILES = {
    "Tile1": {}, "Tile2": {}, "Tile3": {}, "Tile4": {},
    "Tile5": dict(grooves=dict(x=[195.0], y=[325.0]), cable_hole=(130.0, 322.3)),
    "Tile6s": dict(grooves=dict(x=[65.0], y=[325.0]), cable_hole=(130.0, 322.3)),
    "Tile1Mag": {}, "Tile2Mag": {},
}
ALL = ("Tile1", "Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")
# laying order: on every joint the earlier tile has the tab, the later one
# the socket (its plate covers the tab, so it goes on last)
ORDER = {t: i for i, t in enumerate(ALL)} | {"Tile1Mag": 0, "Tile2Mag": 1}
# In R2_Floor-all the corner chamfers of Tile5 and Tile6s meet in a single
# vertical line, which makes the fused mesh non-manifold; a 0.1 mm square
# post fills that line (invisible).
ALL_BRIDGES = [(130.0, 389.24)]


def to_shapely(poly):
    return sg.Polygon(poly["ext"], poly["holes"])


def face(p, z):
    """build123d face at height z from a shapely polygon (normal +z)."""
    p = sg.polygon.orient(p)
    wire = lambda c: Wire.make_polygon([(x, y, z) for x, y in list(c)[:-1]], close=True)  # noqa: E731
    return Face(wire(p.exterior.coords), [wire(h.coords) for h in p.interiors])


def prism(p, z0, z1):
    """Prism over z0..z1 from a shapely (multi)polygon."""
    out = None
    for g in getattr(p, "geoms", [p]):
        if g.area < 1e-4:
            continue
        s = extrude(face(g, z0), z1 - z0, dir=(0, 0, 1))
        out = s if out is None else out + s
    return out


def plate(name, prm, spec, bounds):
    """Top plate with the chamfered top edge. Groove-end notches and the
    cable hole are filled before the chamfer and cut afterwards, so their
    edges stay sharp as in the original."""
    x0, y0, x1, y1 = bounds
    outline = sg.MultiPolygon([to_shapely(p) for p in PROFILES[name]["plate"]]).buffer(0)
    g = spec.get("grooves", {})
    d = prm["groove_depth"]
    fill = []
    for x in g.get("x", []):
        fill += [sg.box(x - d, y0, x + d, y0 + d), sg.box(x - d, y1 - d, x + d, y1)]
    for y in g.get("y", []):
        fill += [sg.box(x0, y - d, x0 + d, y + d), sg.box(x1 - d, y - d, x1, y + d)]
    if "cable_hole" in spec:
        cx, cy = spec["cable_hole"]
        fill.append(sg.Point(cx, cy).buffer(prm["cable_hole_r"] + 0.05, 256))
    tile = sg.box(x0, y0, x1, y1)
    for f in fill:
        outline = outline.union(f.intersection(tile))
    # the measured outline pokes up to 0.03 mm out of the tile; clip it
    outline = outline.buffer(0).intersection(tile).simplify(0.01)
    body = top_chamfer(prism(outline, -prm["plate"], 0.0), prm["top_chamfer"])
    # V-grooves: on top along the line, and down the plate's side at the
    # ends where the original has the V there too (the outer edges)
    measured = sg.MultiPolygon([to_shapely(p) for p in PROFILES[name]["plate"]]).buffer(0)
    notch = lambda x, y: not measured.contains(sg.Point(x, y))  # noqa: E731
    for v in g.get("x", []):
        ends = (notch(v, y0 + 0.3), notch(v, y1 - 0.3))
        body -= groove("x", v, (x0, y0, x1, y1), prm, ends)
    for v in g.get("y", []):
        ends = (notch(x0 + 0.3, v), notch(x1 - 0.3, v))
        body -= groove("y", v, (x0, y0, x1, y1), prm, ends)
    if "cable_hole" in spec:
        cx, cy = spec["cable_hole"]
        body -= Pos(cx, cy, -prm["plate"] / 2) * Cylinder(prm["cable_hole_r"], prm["plate"] + 1)
    return body


def top_chamfer(body, c):
    """45 deg chamfer of all edges of the top face (z = 0). Where OCC cannot
    do them in one go (a short jog next to a long edge, Tile3/4), the edge
    that blocks it is chamfered in a second pass."""
    edges = list(body.edges().filter_by_position(Axis.Z, -1e-3, 1e-3))
    try:
        return chamfer(edges, c)
    except ValueError:
        pass
    for i, e in enumerate(edges):
        try:
            first = chamfer(edges[:i] + edges[i + 1:], c)
        except ValueError:
            continue
        a, b = e.position_at(0), e.position_at(1)
        u = (b - a).normalized()
        rest = []
        for x in first.edges().filter_by_position(Axis.Z, -1e-3, 1e-3):
            m = x.position_at(0.5) - a
            t = m.dot(u)
            if (m - u * t).length < 1e-3 and 0 < t < e.length:
                rest.append(x)
        return chamfer(rest, c)
    raise ValueError("top chamfer failed")


def groove(axis, v, box, prm, ends=(True, True)):
    """V-groove (90 deg, `groove_depth` deep) along x = v or y = v, plus the
    same V down the side faces at the ends flagged in `ends` (low, high)."""
    x0, y0, x1, y1 = box
    d, h = prm["groove_depth"], prm["plate"]
    tri = [(-d, 0.01), (d, 0.01), (0, -d)]          # in (across, z)
    if axis == "x":   # line x = v, running along y
        top = extrude(Plane.XZ.offset(-(y0 - 1)) * Pos(v, 0) * Polygon(*tri, align=None),
                      y1 - y0 + 2, dir=(0, 1, 0))
        tri_side = [(v - d, -0.01), (v + d, -0.01), (v, d)]
        sides = [prism(sg.Polygon([(x, y0 + yy) for x, yy in tri_side]), -h - 0.01, 0.01),
                 prism(sg.Polygon([(x, y1 - yy) for x, yy in tri_side]), -h - 0.01, 0.01)]
    else:             # line y = v, running along x
        top = extrude(Plane.YZ.offset(x0 - 1) * Pos(v, 0) * Polygon(*tri, align=None),
                      x1 - x0 + 2, dir=(1, 0, 0))
        tri_side = [(v - d, -0.01), (v + d, -0.01), (v, d)]
        sides = [prism(sg.Polygon([(x0 + xx, y) for y, xx in tri_side]), -h - 0.01, 0.01),
                 prism(sg.Polygon([(x1 - xx, y) for y, xx in tri_side]), -h - 0.01, 0.01)]
    cut = top
    for s, keep in zip(sides, ends):
        if keep:
            cut += s
    return cut


def joints(name):
    """Joints of a tile: where the original had its alignment-pin holes
    (both skirts are there). Yields (x, y, direction, kind): the point on
    the seam, the direction (dx, dy) the tail points (from the tab tile
    into the socket tile), and "tab" or "socket"."""
    b = PROFILES[name]["bounds"]
    cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
    for pin in PROFILES[name]["pins"]:
        x, y = pin["x"], pin["y"]
        if pin["axis"] == "x":            # seam x = const
            x = round(x / 130) * 130
            d = (1 if x > cx else -1, 0)
        else:
            y = round(y / 130) * 130
            d = (0, 1 if y > cy else -1)
        px, py = x + d[0] * 1, y + d[1] * 1
        other = next(t for t in ALL if PROFILES[t]["bounds"][0] < px < PROFILES[t]["bounds"][3]
                     and PROFILES[t]["bounds"][1] < py < PROFILES[t]["bounds"][4])
        tab = ORDER[name] < ORDER[other]
        # the tail always points from the tab tile into the socket tile
        yield round(x, 1), round(y, 1), d if tab else (-d[0], -d[1]), "tab" if tab else "socket"


def joint(kind, prm):
    """Dovetail in a local frame: seam at u = 0 (x), u > 0 under the
    neighbour, s along the seam (y). Seen from above the tail widens from
    `tail_neck` at the seam to `tail_head` at u = `tail_len`; the
    neighbour is lowered onto it from above, after which the two tiles can
    neither slide apart nor along the seam.

    tab:    the tail plus its root in the tile's own skirt (u -wall..0).
            Its top slopes down from just under the neighbour's plate at
            `tail_overhang` deg, so it prints plate-down without support.
    socket: (block, cut) - a block behind the skirt, fused to the plate,
            and the tail's shape plus `tail_clearance` cut out of it.
    """
    n, h, L = prm["tail_neck"] / 2, prm["tail_head"] / 2, prm["tail_len"]
    H, plate, w = prm["height"], prm["plate"], prm["wall"]
    if kind == "tab":
        plan = sg.Polygon([(-w, -n), (0, -n), (L, -h), (L, h), (0, n), (-w, n)])
        k = 1 / math.tan(math.radians(prm["tail_overhang"]))   # drop per mm
        z0 = -plate - prm["tail_gap"]
        u0 = (z0 + plate - 0.01) / k                           # where the slope meets the plate
        side = sg.Polygon([(-w, -H), (-w, -plate + 0.01), (u0, -plate + 0.01),
                           (L, z0 - k * L), (L, -H)])
        prof = extrude(Plane.XZ * Polygon(*side.exterior.coords[:-1], align=None), h + 1, both=True)
        return prism(plan, -H, -plate + 0.01) & prof
    c = prm["tail_clearance"]
    cut = sg.Polygon([(-1, -n), (0, -n), (L, -h), (L, h), (0, n), (-1, n)]) \
        .buffer(c, join_style=2)
    block = sg.box(0, -h - c - prm["socket_wall"], L + c + prm["socket_wall"],
                   h + c + prm["socket_wall"])
    return prism(block, -H, -plate + 0.01), prism(cut, -H - 0.01, -plate)


def place(solid, x, y, d):
    ang = math.degrees(math.atan2(d[1], d[0]))
    return Pos(x, y, 0) * Rot(0, 0, ang) * solid


def build(name, prm=PARAMS, with_joints=True):
    spec = TILES[name]
    data = PROFILES[name]
    # nominal tile square (the floor is a 130 mm grid)
    b = data["bounds"]
    bounds = [round(b[0] / 130) * 130, round(b[1] / 130) * 130,
              round(b[3] / 130) * 130, round(b[4] / 130) * 130]
    body = plate(name, prm, spec, bounds)
    tile = sg.box(*bounds)
    skirt = sg.MultiPolygon([to_shapely(p) for p in data["skirt"]]).buffer(0).intersection(tile)
    body += prism(skirt, -prm["height"], -prm["plate"] + 0.01)
    # tile number (and sign) under the plate
    for z0, z1, polys in data["relief"]:
        shape = sg.MultiPolygon([to_shapely(p) for p in polys]).buffer(0)
        top = min(z1 + 0.01, -prm["plate"] + 0.01)
        body += prism(shape, z0, top)
    for mg in data["magnets"]:
        depth = prm["magnet_depth"]
        body -= Pos(mg["x"], mg["y"], -prm["plate"] + depth / 2 - 0.01) * \
            Cylinder(prm["magnet_d"] / 2, depth + 0.02)
    if with_joints:
        cuts = []
        for x, y, d, kind in joints(name):
            if kind == "tab":
                body += place(joint("tab", prm), x, y, d)
            else:
                block, cut = joint("socket", prm)
                body += place(block, x, y, d)
                cuts.append(place(cut, x, y, d))
        for c in cuts:
            body -= c
    return body.clean()


JOINT_TEST_CLEARANCES = (0.05, 0.10, 0.15)


def joint_test(prm=PARAMS, clearances=JOINT_TEST_CLEARANCES):
    """Test pieces for the fit: per clearance a pair of small plates
    (30 x 30 mm) with the seam wall and one joint, nothing else - a tab
    piece and a socket piece. Pair i (1, 2, 3 ...) has i small holes
    through both plates. Exported plate-down, as the tiles print."""
    H, pl, w = prm["height"], prm["plate"], prm["wall"]
    half, depth = 15.0, 30.0

    def piece(x0, x1, wall_x0, marks):
        body = top_chamfer(prism(sg.box(x0, -half, x1, half), -pl, 0.0), prm["top_chamfer"])
        body += prism(sg.box(wall_x0, -half, wall_x0 + w, half), -H, -pl + 0.01)
        xm = x1 - 5 if x1 > 0 else x0 + 5
        for k in range(marks):
            body -= Pos(xm, -half + 4 + 3 * k, -pl / 2) * Cylinder(0.75, pl + 1)
        return body

    flip = lambda s: Pos(0, 0, H) * Rot(180, 0, 0) * s   # noqa: E731  plate on the bed
    out = None
    for i, c in enumerate(clearances):
        q = dict(prm, tail_clearance=c)
        tab = piece(0, depth, 0, i + 1) + place(joint("tab", q), 0, 0, (-1, 0))
        block, cut = joint("socket", q)
        sock = piece(-depth, 0, -w, i + 1) + place(block, 0, 0, (-1, 0)) - place(cut, 0, 0, (-1, 0))
        pair = Pos(5, 40 * i, 0) * flip(tab) + Pos(-5, 40 * i, 0) * flip(sock)
        out = pair if out is None else out + pair
    return out.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--only", help="comma-separated tiles, e.g. Tile1,all")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    names = a.only.split(",") if a.only else list(TILES) + ["all", "JointTest"]
    fmts = tuple(a.formats.split(","))
    tiles = {}
    for name in names:
        if name in ("all", "JointTest"):
            continue
        tiles[name] = part = build(name)
        vol = check_solid(part, name)
        print("%s: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (name, *bbox_size(part), vol))
        export_part(part, f"R2_Floor-{name}", root=a.outdir, formats=fmts)
    if "all" in names:
        whole = None
        for name in ALL:
            t = build(name, with_joints=False)   # one piece: no joints
            whole = t if whole is None else whole + t
        for x, y in ALL_BRIDGES:
            whole += prism(sg.box(x - 0.05, y - 0.05, x + 0.05, y + 0.05),
                           -PARAMS["height"], -PARAMS["top_chamfer"])
        # R2_Floor-all stands on z = 0 (the tiles have their top at z = 0)
        whole = Pos(0, 0, PARAMS["height"]) * whole.clean()
        vol = check_solid(whole, "all")
        print("all: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(whole), vol))
        export_part(whole, "R2_Floor-all", root=a.outdir, formats=fmts)
    if "JointTest" in names:
        part = joint_test()
        vol = sum(check_solid(sd, "JointTest") for sd in part.solids())   # two pieces
        print("JointTest: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
        export_part(part, "R2_Floor-JointTest", root=a.outdir, formats=fmts)


if __name__ == "__main__":
    main()
