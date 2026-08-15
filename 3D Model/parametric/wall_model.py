#!/usr/bin/env python3
"""Parametric rebuild of the RasQberry Two wall (Base, Back, Lid).

The geometry is reconstructed as true B-rep solids from measured
cross-sections of the original SketchUp STL exports (see
extract_profiles.py / wall_profiles.json). On top of that this script adds
a parametric "split" feature: each part can be cut into segments joined by
printable dovetail (puzzle) keys, so the 245.7 mm wide wall fits on
printers with beds smaller than the one-piece part.

Outputs (written to ./output):
    R2_Wall-<part>.parametric.stl / .step / .3mf          one-piece
    R2_Wall-<part>.split-A.* / .split-B.*                 split segments

All dimensions in mm.

Requires: build123d  (pip install build123d)
"""
import json
from pathlib import Path

from build123d import (
    Axis, Box, Circle, Location, Plane, Polygon, Pos, Rot,
    export_step, export_stl,
)
from build123d import Mesher

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Where to cut each part, in the part's own coordinates (x, 0 = left edge).
# x = 97 passes only through plain plate/wall regions of all three parts:
# it avoids the hexagon/circle floor openings, the ribs and the lid pegs of
# the base/lid (features at x = 41-46, 51-75, 81-84, 111-135, ...), and the
# vent grilles / screw bosses of the back panel.
# Resulting segment widths: 97 mm + 148.7 mm - both fit a 150 mm bed.
# Add more cut positions for even smaller printers (each must be feature-free).
CUTS = {
    "R2_Wall-Base": [97.0],
    "R2_Wall-Back": [97.0],
    "R2_Wall-Lid": [97.0],
}

CLEARANCE = 0.15   # per-side clearance between dovetail key and pocket
KEY_DEPTH = 9.0    # how far a key reaches into the neighbouring segment
KEY_NECK = 7.0     # key width at the cut plane
KEY_END = 12.0     # key width at its wide (locking) end

# Dovetail key positions per part. "plate": horizontal plate, trapezoid in
# the XY plane extruded over z0..z1 (assembles by dropping vertically).
# "panel": vertical panel, trapezoid in the XZ plane extruded over the
# panel thickness y0..y1 (assembles by pressing horizontally).
KEYS = {
    "R2_Wall-Base": [
        # bottom plate, 3 mm thick
        {"kind": "plate", "at": 15.0, "z0": 0.0, "z1": 3.0},
        {"kind": "plate", "at": 30.0, "z0": 0.0, "z1": 3.0},
        {"kind": "plate", "at": 45.0, "z0": 0.0, "z1": 3.0},
    ],
    "R2_Wall-Back": [
        # main panel, y = 5.7..9.7
        {"kind": "panel", "at": 15.0, "y0": 5.7, "y1": 9.7},
        {"kind": "panel", "at": 40.0, "y0": 5.7, "y1": 9.7},
        {"kind": "panel", "at": 65.0, "y0": 5.7, "y1": 9.7},
    ],
    "R2_Wall-Lid": [
        # top plate, z = 96.97..98.32 (the only solid cross-plate at the
        # cut; stops below the seam grooves on the visible top face)
        {"kind": "plate", "at": 15.0, "z0": 96.97, "z1": 98.32},
        {"kind": "plate", "at": 30.0, "z0": 96.97, "z1": 98.32},
        {"kind": "plate", "at": 45.0, "z0": 96.97, "z1": 98.32},
    ],
}

PROFILES = Path(__file__).parent / "wall_profiles.json"
OUTDIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# Rebuilding the solids from the measured profiles
# ---------------------------------------------------------------------------

def ring_sketch(ring, snap, flip_v):
    """A measured ring (polygon or fitted circle) as a 2D sketch face.

    The measured rings have arbitrary winding; the face is forced to be
    counter-clockwise so its normal is +Z and extrude() goes upwards.
    """
    sign = -1.0 if flip_v else 1.0
    if "circle" in ring:
        cx, cy, r = ring["circle"]
        return Pos(cx, sign * cy) * Circle(r)
    pts = [(x * snap, sign * y * snap) for x, y in ring["pts"]]
    area2 = sum(x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area2 < 0:
        pts.reverse()
    return Polygon(*pts, align=None)


def build_part(data, snap, flip_v=False):
    """Union of one extrusion per measured cross-section band."""
    from build123d import extrude
    solids = []
    for band in data["bands"]:
        z0, z1 = band["z0"], band["z1"]
        for poly in band["polys"]:
            face = ring_sketch(poly["ext"], snap, flip_v)
            for hole in poly["holes"]:
                face -= ring_sketch(hole, snap, flip_v)
            solids.append(extrude(Plane.XY.offset(z0) * face, z1 - z0))
    part = solids[0]
    for s in solids[1:]:
        part = part + s
    return part.clean()


# ---------------------------------------------------------------------------
# Split + dovetail keys
# ---------------------------------------------------------------------------

def trapezoid_prism(cut_x, spec, grow=0.0):
    """Dovetail key: trapezoid flaring from the cut plane into the right
    (+x) segment, extruded across the plate/panel thickness.

    grow > 0 expands the key into the pocket shape (clearance offset).
    """
    neck = KEY_NECK + 2 * grow
    end = KEY_END + 2 * grow
    depth = KEY_DEPTH + grow
    anchor = 2.0  # straight shank reaching back into the left segment
    c, at = cut_x, spec["at"]
    pts = [
        (c - anchor, at - neck / 2), (c, at - neck / 2),
        (c + depth, at - end / 2), (c + depth, at + end / 2),
        (c, at + neck / 2), (c - anchor, at + neck / 2),
    ]

    def ccw_polygon(points):
        area2 = sum(x0 * y1 - x1 * y0
                    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
        if area2 < 0:
            points = list(reversed(points))
        return Polygon(*points, align=None)

    from build123d import extrude
    if spec["kind"] == "plate":
        face = ccw_polygon(pts)
        return extrude(Plane.XY.offset(spec["z0"]) * face, spec["z1"] - spec["z0"])
    # "panel": same profile but standing in the XZ plane, extruded along y.
    # Build in XY with v = -z, extrude over y0..y1, then rotate (see below).
    face = ccw_polygon([(x, -z) for x, z in pts])
    solid = extrude(Plane.XY.offset(spec["y0"]) * face, spec["y1"] - spec["y0"])
    return Rot(X=-90) * solid


def split_part(part, name, size):
    """Cut the part at CUTS[name] and add dovetail keys/pockets."""
    cuts = CUTS[name]
    xmax, ymax, zmax = size
    big = 2 * max(size)
    segments = []
    bounds = [0.0] + list(cuts) + [xmax]
    for i, (x0, x1) in enumerate(zip(bounds[:-1], bounds[1:])):
        region = Location((x0, -big / 2, -big / 2)) * Box(
            x1 - x0, big + ymax, big + zmax, align=None)
        seg = (part & region).clean()
        segments.append(seg)
    # keys: each segment gets tails reaching into the next segment,
    # the next segment gets the matching (expanded) pockets
    for i, cut in enumerate(cuts):
        for spec in KEYS[name]:
            tail = trapezoid_prism(cut, spec)
            pocket = trapezoid_prism(cut, spec, grow=CLEARANCE)
            segments[i] = (segments[i] + tail).clean()
            segments[i + 1] = (segments[i + 1] - pocket).clean()
    return segments


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def export_all(solid, stem):
    export_stl(solid, str(OUTDIR / f"{stem}.stl"))
    export_step(solid, str(OUTDIR / f"{stem}.step"))
    m = Mesher()
    m.add_shape(solid)
    m.write(str(OUTDIR / f"{stem}.3mf"))
    print(f"  wrote {stem}.stl/.step/.3mf")


def main():
    OUTDIR.mkdir(exist_ok=True)
    profiles = json.load(open(PROFILES))
    snap = profiles["snap_mm"]
    for name, data in profiles["parts"].items():
        print(f"=== {name} ===")
        # The back panel's profiles are measured in the (x, z) plane and its
        # bands run along y; build it flipped and rotate into position so the
        # final solid matches the original part's orientation and chirality.
        is_back = data["axis"] == 1
        part = build_part(data, snap, flip_v=is_back)
        if is_back:
            part = Rot(X=-90) * part
        vol_ref = data["mesh_volume_mm3"]
        vol = part.volume
        print(f"  volume {vol / 1000:.2f} cm3 "
              f"(original mesh {vol_ref / 1000:.2f} cm3, "
              f"diff {abs(vol - vol_ref) / vol_ref * 100:.2f}%)")
        export_all(part, f"{name}.parametric")
        if CUTS.get(name):
            segs = split_part(part, name, data["size"])
            for seg, label in zip(segs, "ABCDEFGH"):
                bb = seg.bounding_box()
                print(f"  segment {label}: "
                      f"{bb.max.X - bb.min.X:.1f} x {bb.max.Y - bb.min.Y:.1f}"
                      f" x {bb.max.Z - bb.min.Z:.1f} mm")
                export_all(seg, f"{name}.split-{label}")


if __name__ == "__main__":
    main()
