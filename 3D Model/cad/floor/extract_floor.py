#!/usr/bin/env python3
"""Measure the floor tiles (originals/floor/) into floor_profiles.json.

For each tile it stores what floor_model.py cannot derive from its PARAMS:

- `plate`: outline of the 3 mm top plate (section at z = -1.88), incl. the
  corner chamfers, the key notches, the hex hole and the V-notches where
  the top grooves end.
- `skirt`: outline of the skirt under the plate (section at z = -9.05).
- `relief`: the mirrored tile number (and on Tile6s the sign) under the
  plate, as slabs [z0, z1, polygons].
- `magnets`: magnet pockets in the underside of the plate (x, y, r).

Polygons are {"ext": [[x, y], ...], "holes": [[[x, y], ...], ...]} in
the original's coordinates (the tiles of one floor share one frame).

Usage:  python extract_floor.py   (reads ../../originals/floor/)
"""
import json
from pathlib import Path

import numpy as np
import shapely.geometry as sg
import trimesh

ORIG = Path(__file__).resolve().parents[2] / "originals" / "floor"
TILES = {t: ORIG / f"R2_Floor-{t}.stl" for t in
         ("Tile1", "Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")}
TILES |= {t: ORIG / "Sign Magnet Indent Version" / f"R2_Floor-{t}.stl"
          for t in ("Tile1Mag", "Tile2Mag")}
SIMPLIFY = 0.005


def section(m, z):
    """Shapely (multi)polygon of the mesh section at height z."""
    s = m.section([0, 0, 1], [0, 0, z])
    if s is None:
        return sg.Polygon()
    u = sg.Polygon()
    for p in sorted((sg.Polygon(e[:, :2]) for e in s.discrete), key=lambda p: -p.area):
        u = u.symmetric_difference(p)
    return u.buffer(0)


def geoms(g):
    return [p for p in getattr(g, "geoms", [g]) if p.area > 1e-3]


def snap(v, grid=130.0, tol=0.05):
    """Coordinates within `tol` of a tile edge (the 130 mm grid) are put on
    it: SketchUp left some seam walls 0.025 mm off, so neighbouring tiles
    would touch only along a line."""
    g = round(v / grid) * grid
    return round(g if abs(v - g) < tol else v, 3)


def poly_json(p):
    p = sg.polygon.orient(p.simplify(SIMPLIFY))
    r = lambda c: [[snap(x), snap(y)] for x, y in list(c)[:-1]]  # noqa: E731
    return {"ext": r(p.exterior.coords), "holes": [r(h.coords) for h in p.interiors]}


def relief(m, skirt):
    zs = np.unique(m.vertices[:, 2].round(3))
    zs = zs[(zs > -5.001) & (zs < -2.999)]
    # tile numbers are prisms (-5..-3); the sign on Tile6s is a relief, cut
    # into 0.1 mm slabs
    levels = sorted(set([-5.0, -3.0] + [round(z, 1) for z in zs if -4.45 < z < -3.0]))
    slabs = []
    for z0, z1 in zip(levels, levels[1:]):
        s = section(m, (z0 + z1) / 2).difference(skirt.buffer(0.05))
        ps = [poly_json(p) for p in geoms(s) if p.area > 0.01]
        if ps:
            slabs.append([z0, z1, ps])
    return slabs


def magnets(m):
    out = []
    for p in geoms(section(m, -2.5)):
        for h in p.interiors:
            c = np.array(h.coords)[:-1]
            ctr = c.mean(0)
            out.append({"x": round(ctr[0], 3), "y": round(ctr[1], 3),
                        "r": round(float(np.linalg.norm(c - ctr, axis=1).mean()), 3)})
    return out


def main():
    data = {}
    for name, path in TILES.items():
        m = trimesh.load(path, force="mesh")
        plate = section(m, -1.88)
        skirt = section(m, -9.05)
        data[name] = {
            "plate": [poly_json(p) for p in geoms(plate)],
            "skirt": [poly_json(p) for p in geoms(skirt)],
            "relief": relief(m, skirt),
            "magnets": magnets(m) if name.endswith("Mag") else [],
            "bounds": [round(v, 3) for v in m.bounds.flatten()],
        }
        print(f"{name}: {len(data[name]['relief'])} relief slabs, "
              f"{len(data[name]['magnets'])} magnets")
    out = Path(__file__).with_name("floor_profiles.json")
    out.write_text(json.dumps(data, separators=(",", ":")))
    print("wrote", out)


if __name__ == "__main__":
    main()
