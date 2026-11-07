#!/usr/bin/env python3
"""Measure the prismatic cryostat parts (chandelier, lid) into profiles.

The lid is one clean body and is captured like the wall (../wall/extract_profiles.py):
a stack of constant cross-sections ("bands").

The chandelier is exported by SketchUp as several overlapping, partly open
shells (stem, column with the bottom plate, three plates, a separate tube for
the centre hole), so its merged cross-sections are unreliable. Only the two
free-form outlines are measured here - the stem and the six-armed column -
each from the body it belongs to; cryostat_model.py builds the rest (hex
plates, centre hole) from numbers.

Writes cryo_profiles.json next to this script; cryostat_model.py builds the
solids from it.

Usage:
    git show "origin/3D-model:3D Model/cryostat/R2_ChandelierSingle.stl" > /tmp/src/R2_ChandelierSingle.stl
    git show "origin/3D-model:3D Model/cryostat/R2_CryoLid-Simple.stl"   > /tmp/src/R2_CryoLid-Simple.stl
    git show "origin/3D-model:3D Model/cryostat/Standalone Version/R2_CryoStandaloneGamma.stl" > /tmp/src/R2_CryoStandaloneGamma.stl
    git show "origin/3D-model:3D Model/3D Model - modifications - Jan/October 2025/cryostat/RQB2-R2_CryoStandaloneGamma-jrl04.stl" > /tmp/src/RQB2-R2_CryoStandaloneGamma-jrl04.stl
    python3 extract_cryo_profiles.py /tmp/src
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wall"))
from extract_profiles import LEVEL_MERGE, SNAP, ring_to_json, section_polys  # noqa: E402



def band_region(bodies, level):
    """Union of the cross-sections of all bodies at height `level`."""
    shapes = []
    for b in bodies:
        for ext, holes in section_polys(b, 2, level, (0, 1)):
            shapes.append(Polygon(ext.exterior.coords, [h.exterior.coords for h in holes]))
    region = unary_union(shapes).buffer(0)
    return list(getattr(region, "geoms", [region])) if not region.is_empty else []


def extract(path):
    mesh = trimesh.load(path)
    shift = mesh.bounds[0].copy()
    mesh.apply_translation(-shift)
    bodies = mesh.split(only_watertight=False)
    levels = np.unique(np.round(mesh.vertices[:, 2], 3))
    merged = [float(levels[0])]
    for lv in levels[1:]:
        if lv - merged[-1] > LEVEL_MERGE:
            merged.append(float(lv))
    bands = []
    for z0, z1 in zip(merged[:-1], merged[1:]):
        polys = band_region(bodies, (z0 + z1) / 2)
        bands.append({
            "z0": round(z0, 3), "z1": round(z1, 3),
            "polys": [{"ext": ring_to_json(p.exterior.coords),
                       "holes": [ring_to_json(h.coords) for h in p.interiors]}
                      for p in polys],
        })
    return {"source": Path(path).name, "source_bounds_min": np.round(shift, 3).tolist(),
            "axis": 2, "plane": [0, 1], "size": np.round(mesh.extents, 3).tolist(),
            "bands": bands}


def outline(body, z):
    """Largest closed ring of `body` cut at height z, as snapped points."""
    sec = body.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    rings = [Polygon(np.asarray(r)[:, :2]) for r in sec.discrete]
    ring = max(rings, key=lambda p: p.area)
    return ring_to_json(ring.exterior.coords)


def chandelier(path):
    mesh = trimesh.load(path)
    shift = mesh.bounds[0].copy()
    mesh.apply_translation(-shift)
    bodies = mesh.split(only_watertight=False)
    stem = next(b for b in bodies if b.bounds[1][2] < 15.0)          # z 0 .. 14.7
    column = max((b for b in bodies if b.extents[2] > 40), key=lambda b: b.area)
    return {"source": Path(path).name, "source_bounds_min": np.round(shift, 3).tolist(),
            "size": np.round(mesh.extents, 3).tolist(),
            "stem": outline(stem, 3.0), "column": outline(column, 20.0)}


# Gamma shell: layers (z0, z1, sample height). The sample heights avoid the
# cups (z 13-31, 53-71) and the hinge holes (z 8.2-11.4, 73.2-76.4); those
# are rebuilt from numbers. The two V-grooves round the outside (z 2-3 and
# 84.8-85.8) are captured in 0.1 mm layers (step error <= 0.05 mm).
# The SketchUp mesh is broken (open faces) between z 2.0 and 2.5; those
# layers are cut from the Gamma body in Jan's Tinkercad export instead
# (RQB2-R2_CryoStandaloneGamma-jrl04.stl, which repaired it; same frame
# within 0.005 mm).
REPAIR_Z = (2.0, 2.5)
def _fine(z0, z1, n=10):
    h = (z1 - z0) / n
    return [(round(z0 + i * h, 3), round(z0 + (i + 1) * h, 3), round(z0 + (i + 0.5) * h, 3))
            for i in range(n)]


GAMMA_BANDS = ([(0.0, 2.0, 1.0)] + _fine(2.0, 3.0) + [(3.0, 5.0, 4.0), (5.0, 82.8, 45.0),
               (82.8, 84.8, 83.8)] + _fine(84.8, 85.8) + [(85.8, 91.3, 88.0), (91.3, 93.3, 92.3)])


def gamma_shell(path, repair_path):
    mesh = trimesh.load(path)
    shift = mesh.bounds[0].copy()
    mesh.apply_translation(-shift)
    repair = max(trimesh.load(repair_path).split(only_watertight=False), key=lambda b: b.volume)
    repair.apply_translation(-repair.bounds[0])
    bands = []
    for z0, z1, zs in GAMMA_BANDS:
        src = repair if REPAIR_Z[0] <= zs <= REPAIR_Z[1] else mesh
        polys = section_polys(src, 2, zs, (0, 1))
        bands.append({"z0": z0, "z1": z1, "polys": [
            {"ext": ring_to_json(p.exterior.coords),
             "holes": [ring_to_json(h.exterior.coords) for h in holes]}
            for p, holes in polys]})
    return {"source": Path(path).name, "source_bounds_min": np.round(shift, 3).tolist(),
            "axis": 2, "plane": [0, 1], "size": np.round(mesh.extents, 3).tolist(),
            "bands": bands}


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    data = {"snap_mm": SNAP,
            "R2_CryoLid-Simple": extract(src / "R2_CryoLid-Simple.stl"),
            "R2_ChandelierSingle": chandelier(src / "R2_ChandelierSingle.stl"),
            "R2_CryoStandaloneGamma": gamma_shell(src / "R2_CryoStandaloneGamma.stl",
                                                  src / "RQB2-R2_CryoStandaloneGamma-jrl04.stl")}
    out = Path(__file__).parent / "cryo_profiles.json"
    out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
