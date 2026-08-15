#!/usr/bin/env python3
"""Extract exact cross-section profiles from the original Wall STL files.

The original wall parts (R2_Wall-Base, R2_Wall-Back, R2_Wall-Lid) were
modelled in SketchUp and only exist as STL meshes. Their geometry is almost
purely prismatic: stacks of constant cross-sections along one axis.
This script measures those cross-sections ("bands") and writes them to
wall_profiles.json, which wall_model.py uses to rebuild the parts as true
B-rep solids (STEP/3MF/STL).

Vertex coordinates are snapped to a 0.01 mm grid. Polygon rings whose
vertices lie on a common circle (within 0.05 mm) are stored as circles, so
the rebuilt solids get true cylindrical faces instead of 24-gons.

Usage:
    # fetch the source STLs from the 3D-model branch first, e.g.
    #   git show origin/3D-model:"3D Model/wall/R2_Wall-Base.stl" > /tmp/R2_Wall-Base.stl
    python3 extract_profiles.py <dir-with-source-stls>

Requires: trimesh, shapely, rtree, numpy  (pip install trimesh shapely rtree numpy)
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

# part file -> axis the part is prismatic along, and the two in-plane axes
PARTS = {
    "R2_Wall-Base.stl": {"axis": 2, "plane": (0, 1)},
    "R2_Wall-Back.stl": {"axis": 1, "plane": (0, 2)},
    "R2_Wall-Lid.stl": {"axis": 2, "plane": (0, 1)},
}

SNAP = 0.01          # snap grid for vertex coordinates [mm]
LEVEL_MERGE = 0.05   # merge band boundaries closer than this [mm]
CIRCLE_TOL = 0.05    # max radial deviation for circle recognition [mm]


def fit_circle(pts):
    """Least-squares circle fit; returns (cx, cy, r, max_deviation)."""
    A = np.column_stack([2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))])
    b = (pts ** 2).sum(axis=1)
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = np.sqrt(c + cx ** 2 + cy ** 2)
    dev = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
    return cx, cy, r, dev.max()


def ring_to_json(coords):
    """Encode a closed ring either as a circle or as a vertex list."""
    pts = np.round(np.asarray(coords, dtype=float), 6)
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    if len(pts) >= 12:
        cx, cy, r, dev = fit_circle(pts)
        if dev <= CIRCLE_TOL:
            return {"circle": [round(cx, 3), round(cy, 3), round(r, 3)]}
    return {"pts": np.round(pts / SNAP).astype(int).tolist()}  # ints of 0.01 mm


def section_polys(mesh, axis, level, plane):
    origin = [0.0, 0.0, 0.0]
    origin[axis] = level
    normal = [0.0, 0.0, 0.0]
    normal[axis] = 1.0
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return []
    rings = []
    for line in sec.discrete:
        if len(line) < 4:
            continue
        p = Polygon(np.round(line[:, plane], 4))
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area < 1e-4:
            continue
        rings.append(p)
    rings.sort(key=lambda p: -p.area)
    used = [False] * len(rings)
    out = []
    for i, r in enumerate(rings):
        if used[i]:
            continue
        used[i] = True
        holes = []
        for j in range(i + 1, len(rings)):
            if used[j] or not r.contains(rings[j]):
                continue
            if not any(h.contains(rings[j]) for h in holes):
                holes.append(rings[j])
                used[j] = True
        out.append((r, holes))
    return out


def extract(path, axis, plane):
    mesh = trimesh.load(path)
    shift = mesh.bounds[0].copy()
    mesh.apply_translation(-shift)
    levels = np.unique(np.round(mesh.vertices[:, axis], 3))
    merged = [float(levels[0])]
    for lv in levels[1:]:
        if lv - merged[-1] > LEVEL_MERGE:
            merged.append(float(lv))
    bands = []
    for z0, z1 in zip(merged[:-1], merged[1:]):
        polys = section_polys(mesh, axis, (z0 + z1) / 2, plane)
        bands.append({
            "z0": round(z0, 3),
            "z1": round(z1, 3),
            "polys": [
                {
                    "ext": ring_to_json(p.exterior.coords),
                    "holes": [ring_to_json(h.exterior.coords) for h in holes],
                }
                for p, holes in polys
            ],
        })
    return {
        "source": Path(path).name,
        "source_bounds_min": np.round(shift, 3).tolist(),
        "axis": axis,
        "plane": list(plane),
        "size": np.round(mesh.extents, 3).tolist(),
        "mesh_volume_mm3": round(float(mesh.volume), 1),
        "bands": bands,
    }


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    data = {"snap_mm": SNAP, "parts": {}}
    for fname, cfg in PARTS.items():
        path = src / fname
        if not path.exists():
            print(f"WARNING: {path} not found, skipping")
            continue
        part = extract(path, cfg["axis"], cfg["plane"])
        data["parts"][fname.replace(".stl", "")] = part
        print(f"{fname}: {len(part['bands'])} bands, "
              f"size {part['size']}, volume {part['mesh_volume_mm3'] / 1000:.1f} cm3")
    out = Path(__file__).parent / "wall_profiles.json"
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
