#!/usr/bin/env python3
"""Validate the generated Union parts (trimesh), mirroring the CI STL
analyzer plus model-specific checks.

Per preset (reads output/Union_<preset>_manifest.json written by union_model.py):
  * every STL: watertight, consistent winding, no degenerate faces, exactly
    ONE body, no non-manifold edges; bbox fits the printer bed
  * assembled bbox (from the assembly 3MF) matches the manifest
  * door magnet pockets: the door's top/bottom edge pockets sit exactly above
    the plinth pockets / below the top-plate pockets (same x, y; cavity there)
  * coupling magnets: left-face pockets mirror onto right-face pockets
  * chandelier stays >= 1 mm clear of the door and panels (no collision)
Exit code 1 on any failure.

Usage: python3 validate_union.py [--preset desk|showpiece|all] [--bed 250 220 270]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

OUT = Path(__file__).parent / "output"
FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def mesh_checks(path, bed):
    m = trimesh.load_mesh(path)
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(list(m.geometry.values()))
    name = path.name
    check(m.is_watertight, f"{name}: watertight")
    check(m.is_winding_consistent, f"{name}: consistent winding")
    check(bool(np.all(m.area_faces > 1e-10)), f"{name}: no degenerate faces")
    check(len(m.split(only_watertight=False)) == 1, f"{name}: exactly one body")
    size = m.bounds[1] - m.bounds[0]
    check(all(s <= b + 1e-6 for s, b in zip(sorted(size), sorted(bed))),
          f"{name}: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm fits bed {bed}")
    check(abs(m.bounds[0][2]) < 1e-3, f"{name}: rests on z = 0 (print orientation)")
    return m


def assembled(preset):
    """Assembled, coloured bodies from the 3MF as {name: mesh}."""
    sc = trimesh.load(OUT / f"Union_{preset}_assembly.3mf")
    out = {}
    for node in sc.graph.nodes_geometry:
        gname = sc.graph[node][1]
        mesh = sc.geometry[gname].copy()
        mesh.apply_transform(sc.graph[node][0])
        out[node] = mesh
    return out


def pick(bodies, key):
    for n, m in bodies.items():
        if key in n:
            return m
    raise KeyError(key)


def cavity_at(mesh, pts):
    """True if all pts are OUTSIDE the mesh (i.e. inside a pocket)."""
    return not np.any(mesh.contains(np.asarray(pts)))


def solid_at(mesh, pts):
    return np.all(mesh.contains(np.asarray(pts)))


def validate(preset, bed):
    print(f"=== {preset} ===")
    man = json.loads((OUT / f"Union_{preset}_manifest.json").read_text())
    for part in man["parts"]:
        mesh_checks(OUT / f"Union_{preset}_{part}.stl", bed)
    bodies = assembled(preset)
    body, plinth, door = pick(bodies, "body"), pick(bodies, "plinth"), pick(bodies, "door")
    chand = [m for n, m in bodies.items() if "chandelier" in n]
    # overall size
    allv = np.vstack([m.vertices for m in bodies.values()])
    size = allv.max(0) - allv.min(0)
    want = man["cell"]
    check(abs(size[2] - want[2]) < 0.05 and abs(allv.min(0)[2]) < 1e-3,
          f"assembled height {size[2]:.2f} mm == {want[2]:.2f} (floor at z=0)")
    # door magnets: cavity in door top/bottom edge, in top-plate underside, in plinth top
    mag_d, mag_t = man["magnet"]
    zt, zp = man["z_ceiling"], man["z_plinth_top"]
    dz = man["door"][1]
    for x, y in man["door_magnet_xy"]:
        probe = lambda z: [(x, y, z), (x + mag_d / 4, y, z), (x, y + mag_d / 4, z)]
        check(cavity_at(body, probe(zt + 0.5 * mag_t)) and solid_at(body, probe(zt + mag_t + 0.4)),
              f"top-plate magnet pocket at ({x:.1f}, {y:.1f})")
        check(cavity_at(plinth, probe(zp - 0.5 * mag_t)) and solid_at(plinth, probe(zp - mag_t - 0.4)),
              f"plinth magnet pocket at ({x:.1f}, {y:.1f})")
        ztop = door.bounds[1][2]
        zbot = door.bounds[0][2]
        check(cavity_at(door, probe(ztop - 0.5 * mag_t)) and cavity_at(door, probe(zbot + 0.5 * mag_t)),
              f"door edge magnet pockets at ({x:.1f}, {y:.1f})")
        check(abs(ztop - zt) < 0.35 and abs(zbot - zp) < 0.35,
              f"door spans plinth top -> ceiling (gaps {zbot - zp:.2f} / {zt - ztop:.2f} mm)")
    # coupling magnets: mirror left <-> right
    cm_d, cm_t = man["couple_magnet"]
    xl, xr = plinth.bounds[0][0], plinth.bounds[1][0]
    for y, z in man["couple_magnet_yz"]:
        pl = [(xl + 0.5 * cm_t, y, z), (xl + 0.5 * cm_t, y + cm_d / 4, z)]
        pr = [(xr - 0.5 * cm_t, y, z), (xr - 0.5 * cm_t, y + cm_d / 4, z)]
        check(cavity_at(plinth, pl) and cavity_at(plinth, pr),
              f"coupling magnet pockets at y={y:.1f} on both plinth sides")
    # chandelier clearance
    ch = trimesh.util.concatenate(chand)
    # sample the chandelier surface (full ray-cast containment is slow without embree)
    step = max(1, len(ch.vertices) // 400)
    sample = ch.vertices[::step]
    body_below_ceiling = sample[sample[:, 2] < zt - 0.05]   # ignore the stub inside the top plate
    for other, label, pts in ((door, "door", sample), (body, "body", body_below_ceiling)):
        _, dist, _ = trimesh.proximity.closest_point(other, pts)
        inside = other.contains(pts)
        clear = dist.min() if not inside.any() else -dist[inside].max()
        check(not inside.any() and clear >= 1.0,
              f"chandelier clearance to {label}: {clear:.2f} mm ({len(pts)} sample points)")
    # the chandelier stub must actually sit in the ceiling hole
    top = ch.bounds[1][2]
    check(top > zt + 0.5, f"chandelier stub reaches into the top plate ({top - zt:.2f} mm)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="all")
    ap.add_argument("--bed", nargs=3, type=float, default=[250, 220, 270],
                    help="printer volume X Y Z in mm (default: Prusa Core One)")
    a = ap.parse_args()
    presets = ["desk", "showpiece"] if a.preset == "all" else [a.preset]
    for p in presets:
        if (OUT / f"Union_{p}_manifest.json").exists():
            validate(p, a.bed)
        else:
            print(f"=== {p}: no output, skipped")
    if FAILS:
        print(f"\n{len(FAILS)} check(s) FAILED")
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
