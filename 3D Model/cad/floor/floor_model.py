#!/usr/bin/env python3
"""Parametric rebuild of the floor tiles (R2_Floor-Tile1..6s, -Tile1Mag/2Mag, -all).

The floor is 260 x 390 mm in six 130 x 130 tiles (2 x 3), 10 mm high:

- a 3 mm top plate with a 0.75 mm 45 deg chamfer round its top edges, so
  neighbouring tiles meet in a small V;
- a 3 mm skirt underneath (z -10 .. -3) round the tile, open where cables
  or the server/cryostat feet need room;
- horizontal holes (Ø 3.2) through the skirt where two tiles meet, for
  alignment pins (filament or 3 mm dowels);
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

Usage:  python floor_model.py [--outdir ROOT] [--only Tile1,Tile5,...]
"""
import argparse
import json
import sys
from pathlib import Path

import shapely.geometry as sg
from build123d import (Axis, Cylinder, Face, Plane, Polygon, Pos, Rot, Wire, chamfer,
                       extrude)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PROFILES = json.loads(Path(__file__).with_name("floor_profiles.json").read_text())

PARAMS = dict(
    plate=3.0, height=10.0,      # plate thickness, total height (z -10 .. 0)
    top_chamfer=0.75,
    groove_depth=0.75,           # V-grooves on top (90 deg)
    pin_d=3.2, pin_z=-6.5, wall=3.0,
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


def build(name, prm=PARAMS):
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
    # alignment pin holes, across the skirt wall
    r, L = prm["pin_d"] / 2, prm["wall"] + 1.0
    for pin in data["pins"]:
        rot = Rot(0, 90, 0) if pin["axis"] == "x" else Rot(90, 0, 0)
        body -= Pos(pin["x"], pin["y"], prm["pin_z"]) * rot * Cylinder(r, L)
    # tile number (and sign) under the plate
    for z0, z1, polys in data["relief"]:
        shape = sg.MultiPolygon([to_shapely(p) for p in polys]).buffer(0)
        top = min(z1 + 0.01, -prm["plate"] + 0.01)
        body += prism(shape, z0, top)
    for mg in data["magnets"]:
        depth = prm["magnet_depth"]
        body -= Pos(mg["x"], mg["y"], -prm["plate"] + depth / 2 - 0.01) * \
            Cylinder(prm["magnet_d"] / 2, depth + 0.02)
    return body.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--only", help="comma-separated tiles, e.g. Tile1,all")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    names = a.only.split(",") if a.only else list(TILES) + ["all"]
    fmts = tuple(a.formats.split(","))
    tiles = {}
    for name in names:
        if name == "all":
            continue
        tiles[name] = part = build(name)
        vol = check_solid(part, name)
        print("%s: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (name, *bbox_size(part), vol))
        export_part(part, f"R2_Floor-{name}", root=a.outdir, formats=fmts)
    if "all" in names:
        whole = None
        for name in ALL:
            t = tiles.get(name) or build(name)
            whole = t if whole is None else whole + t
        for x, y in ALL_BRIDGES:
            whole += prism(sg.box(x - 0.05, y - 0.05, x + 0.05, y + 0.05),
                           -PARAMS["height"], -PARAMS["top_chamfer"])
        # R2_Floor-all stands on z = 0 (the tiles have their top at z = 0)
        whole = Pos(0, 0, PARAMS["height"]) * whole.clean()
        vol = check_solid(whole, "all")
        print("all: size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(whole), vol))
        export_part(whole, "R2_Floor-all", root=a.outdir, formats=fmts)


if __name__ == "__main__":
    main()
