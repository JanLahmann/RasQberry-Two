#!/usr/bin/env python3
"""Parametric rebuild of the narrow RTE server body (jrl02 variant).

Rebuilds `3D Model/3D Model - modifications - Jan/October 2025/RTE/
RQB2-R2_NarrowServerSingle-jrl02.stl` (SketchUp original, mesh only) as a
CAD solid. All dimensions were measured from that STL (see README.md); every
tunable is in the PARAMS dict below.

Shape: an open-top box 38.1 x 23.25 x 93.3 mm with a socket for the lid at
the top, a V-groove round the bottom and the top, shallow recessed panels on
all four faces, a 10 x 47 grid of ventilation holes through both narrow side
walls, and inside two 1 mm mounting plates (front and back) with two
cup-shaped cradles and two half-round ribs each.

Coordinates: x = width (side walls with the holes at x = +/-), y = depth
(front at -y), z = up; the box stands on z = 0, centred on x = y = 0.

Usage:  python narrow_server.py [--variant jrl02|original] [--outdir ROOT] [--formats stl,step]
"""
import argparse
import sys
from pathlib import Path

from build123d import (
    Align, Box, Circle, Cylinder, GridLocations, Plane, Polygon, Pos,
    Rectangle, Rot, Sketch, extrude, loft,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rqb_params  # noqa: E402
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PARAMS = dict(
    # outer box
    width=rqb_params.RTE_WIDTH, depth=rqb_params.RTE_DEPTH,
    height=rqb_params.BODY_HEIGHT,
    edge_chamfer=0.5,            # the four vertical edges
    floor=3.0,                   # floor thickness
    # cavity (front wall 1.8 mm, back wall 2.7 mm, side walls 2.2 mm)
    cavity_x=(-16.85, 16.85), cavity_y=(-9.83, 8.92), cavity_top=86.55,
    # lid socket: thin rim at the top
    socket_x=(-18.05, 18.05), socket_y=(-10.625, 10.625),
    # V-grooves round the outside (depth = half width, 45 deg flanks)
    grooves_z=(2.5, 85.3), groove_depth=0.5,
    # recessed panels (z range, half width along the face, depth)
    panel_z=(5.0, 82.8),
    panel_front=dict(half=17.05, depth=0.19),
    panel_back=dict(half=17.05, depth=0.30),
    panel_side=dict(half=9.13, depth=0.20),
    # ventilation holes through both side walls
    hole_dia=1.18, hole_cols=10, hole_rows=47,
    hole_pitch_y=1.654, hole_pitch_z=1.650,
    hole_centre=(0.04, 44.0),    # (y, z) of the grid centre
    # mounting plates on the inside of the front and back wall
    plate_half=15.0, plate_thick=1.0, plate_top=78.0,
    # cups (U ring + closing D plate) standing on each plate
    cup_z=(21.76, 61.76),        # centre of the outer arc, lower and upper cup
    cup_r_out=13.0, cup_r_in=9.0, cup_in_dz=-0.76,  # inner arc centre offset
    cup_arm=2.64,                # straight part above the arc centre
    cup_ring=2.02, cup_face=1.23,  # depth of the U ring and the D face
    # half-round ribs on each plate
    rib_z=(29.64, 69.64), rib_half=7.5, rib_chord=2.0, rib_height=0.75,
    # which inner walls carry plate, cups and ribs (Jan's jrl02: both)
    mount_walls=("front", "back"), plates=True, ribs=True,
    cup_pocket=None,             # (radius, depth) of a disc cut into the wall behind each cup
    open_front=False,            # front wall cut away over the cavity width (paired servers)
)

# The original R2_NarrowServerSingle (SketchUp) differs from jrl02 only
# inside: no plates and no ribs, two cups on the back wall only, standing
# straight on the wall, with concentric arcs (R 10 / R 8) and an R 8 pocket
# 0.5 mm deep in the wall behind each cup; slightly bigger holes and a
# slightly deeper front panel.
VARIANTS = {
    "jrl02": dict(name="RQB2-R2_NarrowServerSingle-jrl02"),
    "original": dict(
        name="R2_NarrowServerSingle",
        mount_walls=("back",), plates=False, ribs=False,
        cup_z=(23.0, 63.3), cup_r_out=10.0, cup_r_in=8.0, cup_in_dz=0.0,
        cup_arm=4.0, cup_ring=2.0, cup_face=1.2, cup_pocket=(8.0, 0.5),
        hole_dia=1.2, panel_front=dict(half=17.05, depth=0.21),
    ),
}


def variant(name):
    """PARAMS with a variant's changes applied."""
    p = dict(PARAMS)
    p.update({k: v for k, v in VARIANTS[name].items() if k != "name"})
    return p


def _box(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=Align.MIN)


def outline(p, inset=0.0):
    """The chamfered outer footprint, optionally inset."""
    w, d, c = p["width"] - 2 * inset, p["depth"] - 2 * inset, p["edge_chamfer"]
    c = max(c - inset * 0.4142, 0.0)  # inset of a 45 deg chamfer
    hw, hd = w / 2, d / 2
    return Polygon((-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
                   (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c),
                   align=None)


def groove(p, zc):
    """V cut round the outline, centred at height zc, 45 deg flanks."""
    t = p["groove_depth"]
    slab = extrude(Plane.XY.offset(zc - t) * outline(p), 2 * t)
    full_lo = Plane.XY.offset(zc - t) * outline(p)
    mid = Plane.XY.offset(zc) * outline(p, t)
    full_hi = Plane.XY.offset(zc + t) * outline(p)
    return slab - (loft([full_lo, mid]) + loft([mid, full_hi]))


def cup(p, y_plate, sign, zc):
    """U ring + closing D face standing on a plate face at y = y_plate and
    growing in direction sign (+1 = +y). Profile drawn in x/z."""
    ro, ri, top = p["cup_r_out"], p["cup_r_in"], zc + p["cup_arm"]
    zi = zc + p["cup_in_dz"]
    cut_top = Pos(0, top + 50) * Rectangle(200, 100)
    outer = (Pos(0, zc) * Circle(ro) + Pos(0, (zc + top) / 2) * Rectangle(2 * ro, top - zc)) - cut_top
    inner = Pos(0, zi) * Circle(ri) + Pos(0, (zi + top + 5) / 2) * Rectangle(2 * ri, top + 5 - zi)
    ring = outer - inner

    def at(y):  # local x = world x, local y = world z, normal = -y
        return Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    r = extrude(at(y_plate) * ring, -sign * p["cup_ring"])
    f = extrude(at(y_plate + sign * p["cup_ring"]) * outer, -sign * p["cup_face"])
    return r + f


def rib(p, y_plate, sign, zc):
    c, h, L = p["rib_chord"], p["rib_height"], p["rib_half"]
    r = (c * c / 4 + h * h) / (2 * h)
    yc = y_plate + sign * (h - r)
    cyl = Pos(0, yc, zc) * Rot(0, 90, 0) * Cylinder(r, 2 * L)
    keep = _box(-L, L, *sorted((y_plate, y_plate + sign * (h + 0.01))), zc - r, zc + r)
    return cyl & keep


def mount_insert(p=PARAMS, trim_lo=0.0, trim_hi=0.0):
    """One mounting plate with its cups and ribs, as a separate solid.

    Back face on y = 0, cups growing towards +y, centred on x = 0, standing on
    the floor (z from p["floor"] to p["plate_top"], as inside the server).
    trim_lo / trim_hi cut that much off the -x / +x end (plate, cups and
    all). Also used by ../cryostat/cryostat_model.py (Jan's Gamma jrl04).
    """
    ph, pt, fl = p["plate_half"], p["plate_thick"], p["floor"]
    part = _box(-ph, ph, 0.0, pt, fl, p["plate_top"])
    for z in p["cup_z"]:
        part += cup(p, pt - 0.01, +1, z)
    for z in p["rib_z"]:
        part += rib(p, pt - 0.01, +1, z)
    if trim_lo > 0:
        part -= _box(-ph - 1, -ph + trim_lo, -1, 10, fl - 1, p["plate_top"] + 1)
    if trim_hi > 0:
        part -= _box(ph - trim_hi, ph + 1, -1, 10, fl - 1, p["plate_top"] + 1)
    return part


def build(p=PARAMS):
    H, fl = p["height"], p["floor"]
    body = extrude(outline(p), H)
    for zc in p["grooves_z"]:
        body -= groove(p, zc)

    # recessed panels
    z0, z1 = p["panel_z"]
    hy, hx = p["depth"] / 2, p["width"] / 2
    f, b, s = p["panel_front"], p["panel_back"], p["panel_side"]
    body -= _box(-f["half"], f["half"], -hy - 1, -hy + f["depth"], z0, z1)
    body -= _box(-b["half"], b["half"], hy - b["depth"], hy + 1, z0, z1)
    body -= _box(-hx - 1, -hx + s["depth"], -s["half"], s["half"], z0, z1)
    body -= _box(hx - s["depth"], hx + 1, -s["half"], s["half"], z0, z1)

    # cavity and lid socket
    cx, cy = p["cavity_x"], p["cavity_y"]
    body -= _box(cx[0], cx[1], cy[0], cy[1], fl, H + 1)
    sx, sy = p["socket_x"], p["socket_y"]
    body -= _box(sx[0], sx[1], sy[0], sy[1], p["cavity_top"], H + 1)
    if p["open_front"]:
        body -= _box(cx[0], cx[1], -hy - 1, cy[0] + 0.01, fl, H + 1)

    # ventilation holes: one grid, extruded through each side wall only
    yc, zc = p["hole_centre"]
    for x_in, x_out in ((cx[0], -hx), (cx[1], hx)):
        sk = Sketch() + [Pos(yc, zc) * loc * Circle(p["hole_dia"] / 2)
                         for loc in GridLocations(p["hole_pitch_y"], p["hole_pitch_z"],
                                                  p["hole_cols"], p["hole_rows"])]
        lo, hi = sorted((x_in, x_out))
        pln = Plane(origin=(lo - 0.1, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        body -= extrude(pln * sk, hi - lo + 0.2)

    # plates, cups and ribs (front plate grows +y, back plate grows -y)
    ph, ptop = p["plate_half"], p["plate_top"]
    pt = p["plate_thick"] if p["plates"] else 0.0
    walls = {"front": (cy[0], +1), "back": (cy[1], -1)}
    for wall_y, sign in (walls[w] for w in p["mount_walls"]):
        face_y = wall_y + sign * pt
        if p["plates"]:
            body += _box(-ph, ph, *sorted((wall_y - sign * 0.01, face_y)), fl - 0.01, ptop)
        if p["cup_pocket"]:
            r, d = p["cup_pocket"]
            for z in p["cup_z"]:
                pln = Plane(origin=(0, wall_y + sign * 0.01, z), x_dir=(1, 0, 0), z_dir=(0, -sign, 0))
                body -= extrude(pln * Circle(r), d + 0.01)
        for z in p["cup_z"]:
            body += cup(p, face_y - sign * 0.01, sign, z)
        if p["ribs"]:
            for z in p["rib_z"]:
                body += rib(p, face_y - sign * 0.01, sign, z)
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="jrl02")
    a = ap.parse_args()
    part = build(variant(a.variant))
    vol = check_solid(part, "NarrowServerSingle")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    names = [VARIANTS[a.variant]["name"]]
    if a.variant == "original":   # the same part in the standalone set
        names.append("R2_NarrowServerSingle-standalone")
    for name in names:
        export_part(part, name, root=a.outdir, formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
