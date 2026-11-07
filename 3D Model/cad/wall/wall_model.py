#!/usr/bin/env python3
"""Parametric rebuild of the RasQberry Two wall (Base, Back, Back+13, Lid).

The geometry is reconstructed as true B-rep solids from measured
cross-sections of the original SketchUp STL exports (see
extract_profiles.py / wall_profiles.json). On top of that this script adds
a parametric "split" feature: each part can be cut into segments joined by
printable dovetail (puzzle) keys, so the 245.7 mm wide wall fits on
printers with beds smaller than the one-piece part.

Outputs (written to ../../print/wall/; see rqb_cad.PARTS):
    <part>.stl / .step / .3mf             one-piece
    <part>.split-A.* / .split-B.*         split segments

All dimensions in mm.

Requires: build123d  (pip install build123d); shared helpers in rqb_cad.py
"""
import json
import sys
from pathlib import Path

from build123d import Circle, Plane, Polygon, Pos, Rot, extrude

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rqb_params  # noqa: E402
from rqb_cad import export_part, split_part  # noqa: E402

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

# shared fit and dovetail values (rqb_params.py)
CLEARANCE = rqb_params.CLEARANCE                 # per-side key/pocket clearance
KEY_DEPTH = rqb_params.DOVETAIL["key_depth"]     # reach into the neighbour
KEY_NECK = rqb_params.DOVETAIL["key_neck"]       # key width at the cut plane
KEY_END = rqb_params.DOVETAIL["key_end"]         # width at the locking end

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

# Variants: a measured part plus a few edits, in the part's own coordinates
# (x from the left edge, as in wall_profiles.json).
#   add_prisms: (x0, x1, [(y, z), ...]) a y/z polygon extruded from x0 to x1,
#               fused onto the part
#   closed_bottom: fill the openings in the floor plate (band starting at z 0)
#   move: (u0, u1, v0, v1, dv) every measured ring lying wholly inside the
#         box u0..u1 x v0..v1 (profile plane, mm) is moved by dv along v
#   fill: [(u0, u1, v0, v1), ...] holes lying wholly inside a box are closed
# The jrl variants are Jan's Tinkercad edits of the base (October 2025,
# "3D Model - modifications - Jan"); the edit was found by a boolean
# difference of his STL against the original. mesh_volume_mm3 = his mesh
# (inflated by overlapping bodies Tinkercad leaves inside the part).
# jrl01: the sloped underside on the seam centre thickened by 1 mm over 6 mm
# width (slope z = 69.52 + 3 (y - 13) lowered to 68.52 + 3 (y - 13)). The
# strip reaches 1.1 mm up into the solid so its top edge does not coincide
# with the existing edge at (y 15, z 75.52) - that meshes into a leaky STL.
JRL01_RAISE = (119.86, 125.86, [(13.0, 68.52), (15.0, 74.52), (15.0, 75.62), (13.0, 70.62)])
# Back+13: the Raspberry Pi mount 13 mm higher. Moved: the four screw bosses
# (x 126.8 / 184.8, height 7 and 56 -> 20 and 69), both round openings with
# their grilles and the frame around the left opening. The recess at the top
# edge (x 112.7..132.7), where the upper left boss now sits, is filled.
# Outline, side pegs and the two small round holes stay. (Found by sections of
# R2_Wall-Back+13.stl against R2_Wall-Back.stl.)
BACK_PLUS = 13.0
VARIANTS = {
    "R2_Wall-Back+13": dict(base="R2_Wall-Back", move=(40.0, 200.0, 0.0, 65.0, BACK_PLUS),
                            fill=[(110.0, 135.0, 65.0, 80.0)],
                            mesh_volume_mm3=73153.5),
    "R2_Wall-Base-jrl01-2": dict(base="R2_Wall-Base", add_prisms=[JRL01_RAISE],
                                 mesh_volume_mm3=106853.3),
    "R2_Wall-Base-jrl01-2-nofloor": dict(base="R2_Wall-Base", add_prisms=[JRL01_RAISE],
                                         closed_bottom=True, mesh_volume_mm3=126653.3),
}

PROFILES = Path(__file__).parent / "wall_profiles.json"


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


def move_rings(data, snap, u0, u1, v0, v1, dv, fill=()):
    """Copy of `data` with every ring inside the box moved by dv along v,
    and the holes inside any `fill` box removed."""
    def inside(r, u0=u0, u1=u1, v0=v0, v1=v1):
        if "circle" in r:
            cx, cy, rad = r["circle"]
            return u0 <= cx - rad and cx + rad <= u1 and v0 <= cy - rad and cy + rad <= v1
        us = [x * snap for x, _ in r["pts"]]
        vs = [y * snap for _, y in r["pts"]]
        return u0 <= min(us) and max(us) <= u1 and v0 <= min(vs) and max(vs) <= v1

    def moved(r):
        if not inside(r):
            return r
        if "circle" in r:
            cx, cy, rad = r["circle"]
            return {**r, "circle": [cx, cy + dv, rad]}
        return {**r, "pts": [[x, y + dv / snap] for x, y in r["pts"]]}

    def kept(h):
        return not any(inside(h, *box) for box in fill)

    bands = [{**b, "polys": [{"ext": moved(p["ext"]),
                              "holes": [moved(h) for h in p["holes"] if kept(h)]}
                             for p in b["polys"]]} for b in data["bands"]]
    return {**data, "bands": bands}


def build_part(data, snap, flip_v=False, closed_bottom=False):
    """Union of one extrusion per measured cross-section band."""
    solids = []
    for band in data["bands"]:
        z0, z1 = band["z0"], band["z1"]
        for poly in band["polys"]:
            face = ring_sketch(poly["ext"], snap, flip_v)
            if not (closed_bottom and z0 == 0.0):  # closed: keep the floor solid
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
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--only", help="comma-separated part names")
    a = ap.parse_args()
    profiles = json.load(open(PROFILES))
    snap = profiles["snap_mm"]
    jobs = [(name, data, {}) for name, data in profiles["parts"].items()]
    jobs += [(name, profiles["parts"][v["base"]], v) for name, v in VARIANTS.items()]
    if a.only:
        jobs = [j for j in jobs if j[0] in a.only.split(",")]
    for name, data, variant in jobs:
        print(f"=== {name} ===")
        # The back panel's profiles are measured in the (x, z) plane and its
        # bands run along y; build it flipped and rotate into position so the
        # final solid matches the original part's orientation and chirality.
        is_back = data["axis"] == 1
        if "move" in variant:
            data = move_rings(data, snap, *variant["move"], fill=variant.get("fill", ()))
        part = build_part(data, snap, flip_v=is_back,
                          closed_bottom=variant.get("closed_bottom", False))
        if is_back:
            part = Rot(X=-90) * part
        for x0, x1, yz in variant.get("add_prisms", []):
            pln = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
            part = (part + extrude(pln * Polygon(*yz, align=None), x1 - x0)).clean()
        vol_ref = variant.get("mesh_volume_mm3", data["mesh_volume_mm3"])
        vol = part.volume
        print(f"  volume {vol / 1000:.2f} cm3 "
              f"(original mesh {vol_ref / 1000:.2f} cm3, "
              f"diff {abs(vol - vol_ref) / vol_ref * 100:.2f}%)")
        export_part(part, name, root=a.outdir)
        # variants are split like their base part
        base = variant.get("base", name)
        if CUTS.get(base):
            segs = split_part(part, data["size"], CUTS[base], KEYS[base],
                              CARVE.get(base, []), clearance=CLEARANCE,
                              key_depth=KEY_DEPTH, key_neck=KEY_NECK, key_end=KEY_END)
            for seg, label in zip(segs, "ABCDEFGH"):
                bb = seg.bounding_box()
                print(f"  segment {label}: "
                      f"{bb.max.X - bb.min.X:.1f} x {bb.max.Y - bb.min.Y:.1f}"
                      f" x {bb.max.Z - bb.min.Z:.1f} mm")
                export_part(seg, name, f".split-{label}", root=a.outdir)


if __name__ == "__main__":
    main()
