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

Requires: build123d  (pip install build123d); shared helpers in rqb_cad.py
"""
import json
from pathlib import Path

from build123d import Circle, Plane, Polygon, Pos, Rot, extrude

from rqb_cad import export_all, split_part

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Where to cut each part, in the part's own coordinates (x, 0 = left edge).
#
# Base and Lid are cut at x = 122.86 - the CENTRE of the middle facade seam
# (the wall's five seam lines - lid pegs plus the matching grooves on the
# lid's top face - sit at x = 43.86, 82.86, 122.86, 162.86, 201.86). This
# way the visible joint coincides with a pre-existing seam: on the base the
# cut passes through the gap in the front lip (121.26..124.46), on the lid
# the front peg is kept in one piece via CARVE below and the joint follows
# the seam line. Inside, the cut crosses the base's circular floor opening
# and halves the middle rib and the lid's centre post lengthwise - purely
# interior faces (base rib and lid post halves still mate after assembly).
# Segments are symmetric: ~123 mm each, both fit a 150 mm bed.
#
# The Back keeps x = 97: at 122.86 its screw bosses (123.8..129.8) are in
# the way, its rear face has no seam lines anyway, and staggering the back
# joint against the base/lid joint stiffens the assembled wall.
#
# Any added cut position must avoid part features (see README).
SEAM_CENTRE = 122.86
CUTS = {
    "R2_Wall-Base": [SEAM_CENTRE],
    "R2_Wall-Back": [97.0],
    "R2_Wall-Lid": [SEAM_CENTRE],
}

# Regions re-assigned wholly to one side of a cut (axis-aligned boxes,
# (xmin, ymin, zmin, xmax, ymax, zmax)). Used to keep a feature that
# straddles a cut in one piece instead of slicing it. "cut" is the index
# into CUTS[part]; "to" is "left" or "right".
CARVE = {
    # keep the lid's free-hanging front peg (x 121.36..124.36, y 0.2..6.2,
    # z 0..83.72) in one piece on the left segment; above z 83.72 the wall
    # is solid and the flat cut continues on the seam centre line
    "R2_Wall-Lid": [
        {"cut": 0, "to": "left", "box": (121.36, -1.0, -1.0, 124.36, 7.0, 83.72)},
    ],
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
        # bottom plate, 3 mm thick; y positions clear the circular floor
        # opening (centre y 27.3, r 11.0) that the seam cut passes through.
        # The front key is narrower: it has to fit between the front-lip
        # slot recess (up to y 6.1) and the circular opening (from y 16.3).
        {"kind": "plate", "at": 11.0, "z0": 0.0, "z1": 3.0, "neck": 5.0, "end": 8.0},
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
# Main
# ---------------------------------------------------------------------------

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
        export_all(part, f"{name}.parametric", OUTDIR)
        if CUTS.get(name):
            segs = split_part(part, data["size"], CUTS[name], KEYS[name],
                              CARVE.get(name, []), clearance=CLEARANCE,
                              key_depth=KEY_DEPTH, key_neck=KEY_NECK, key_end=KEY_END)
            for seg, label in zip(segs, "ABCDEFGH"):
                bb = seg.bounding_box()
                print(f"  segment {label}: "
                      f"{bb.max.X - bb.min.X:.1f} x {bb.max.Y - bb.min.Y:.1f}"
                      f" x {bb.max.Z - bb.min.Z:.1f} mm")
                export_all(seg, f"{name}.split-{label}", OUTDIR)


if __name__ == "__main__":
    main()
