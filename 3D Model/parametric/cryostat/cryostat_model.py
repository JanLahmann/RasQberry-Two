#!/usr/bin/env python3
"""Parametric rebuild of the cryostat parts: lid, chandelier, standalone body
(Gamma), and Jan's variants (lid with chandeliers jrl01, Gamma jrl04).
See README.md for what each part is and how close the rebuild is.

Parts (SketchUp originals on branch 3D-model, `3D Model/cryostat/`):
  R2_CryoLid-Simple     hexagonal lid, 76.2 x 66.0 x 20.7 mm, with three sockets
                        (1 mm hexagonal recess + 8 mm hole) on its underside
  R2_ChandelierSingle   20.2 x 17.5 x 64.2 mm: stem, six-armed column, four
                        hexagonal plates, 4 mm hole through the middle

Assembly (Jan, October 2025, Tinkercad; `3D Model - modifications - Jan/
October 2025/cryostat/RQB2-Cryostat-jrl01.stl`): the lid turned over (sockets
up) with three chandeliers hanging from it upside down - each chandelier's top
plate stands in a socket recess (0.1 mm overlap so they fuse). Printed as one
piece, lid down. Jan placed the chandeliers by hand, up to 0.27 mm off the
sockets; here they sit exactly on the socket centres.

The lid's cross-sections and the chandelier's two free-form outlines (stem,
column) come from cryo_profiles.json (see extract_cryo_profiles.py); the rest
is built from the numbers in CHANDELIER below.

Usage:  python cryostat_model.py [--outdir DIR]
"""
import argparse
import json
import sys
from pathlib import Path

from build123d import (Circle, Cylinder, Plane, Polygon, Pos, Rectangle, Rot,
                       RegularPolygon, extrude)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from rqb_cad import bbox_size, check_solid, export_all  # noqa: E402
from wall_model import build_part, ring_sketch  # noqa: E402
sys.path.insert(0, str(HERE.parent / "rte"))
from narrow_server import mount_insert  # noqa: E402

PROFILES = HERE / "cryo_profiles.json"

CHANDELIER = dict(
    centre=(10.088, 8.7365),     # hex centre in the outline coordinates
    hex_r=10.088,                # plate circumradius (17.47 mm across flats)
    hole_r=1.988,                # centre hole
    stem=(0.0, 14.7),            # z range of the stem
    column=(14.7, 64.2),         # six-armed column (bottom plate included)
    plates=[(14.7, 16.2), (31.029, 32.529), (46.2, 47.7), (62.7, 64.2)],
)

ASSEMBLY = dict(
    overlap=0.1,                 # chandelier plate sunk into the socket recess
    recess=1.0,                  # socket recess depth (lid band z 0..1)
)


def _z(face, z0, z1):
    return extrude(Plane.XY.offset(z0) * face, z1 - z0)


def chandelier(prof, p=CHANDELIER):
    """Upright chandelier, hex centre at x = y = 0, standing on z = 0."""
    snap = prof["snap_mm"]
    c = prof["R2_ChandelierSingle"]
    cx, cy = p["centre"]
    stem = Pos(-cx, -cy) * ring_sketch(c["stem"], snap, False)
    column = Pos(-cx, -cy) * ring_sketch(c["column"], snap, False)
    body = _z(stem, *p["stem"]) + _z(column, *p["column"])
    hexagon = RegularPolygon(p["hex_r"], 6)          # corners on +/- x
    for z0, z1 in p["plates"]:
        body += _z(hexagon, z0, z1)
    body -= _z(Circle(p["hole_r"]), -1, p["column"][1] + 1)
    return body.clean()


def lid(prof):
    """Lid as in the original: sockets on the underside, centred on x = y = 0."""
    d = prof["R2_CryoLid-Simple"]
    part = build_part(d, prof["snap_mm"])
    sx, sy, _ = d["size"]
    return Pos(-sx / 2, -sy / 2, 0) * part


def socket_centres(prof):
    """Centres of the three socket holes, relative to the lid centre."""
    d = prof["R2_CryoLid-Simple"]
    sx, sy, _ = d["size"]
    band = next(b for b in d["bands"] if b["z0"] == 1.0)
    return [(h["circle"][0] - sx / 2, h["circle"][1] - sy / 2)
            for poly in band["polys"] for h in poly["holes"] if "circle" in h]


def jrl01(prof, a=ASSEMBLY):
    """Lid turned over with three chandeliers hanging upside down from it."""
    lid_h = prof["R2_CryoLid-Simple"]["size"][2]
    top = Pos(0, 0, lid_h) * Rot(0, 180, 0) * lid(prof)       # sockets now on top
    ch = chandelier(prof)
    ch_h = CHANDELIER["column"][1]
    z0 = lid_h - a["recess"] - a["overlap"]                    # plate face in the recess
    part = top
    for x, y in socket_centres(prof):
        # turning the lid over mirrors x; the chandelier is turned over too
        part += Pos(-x, y, z0 + ch_h) * Rot(0, 180, 0) * ch
    return part.clean()


GAMMA = dict(
    corner_r=38.103,             # outer hexagon, corners on +/- x
    inner_apothem=30.6,          # inside face of the five walls
    walls=(90, 30, 150, -30, -150),   # outward normal of each wall (deg); front open
    hinge_r=1.588, hinge_y=-27.421, hinge_z=(9.8, 74.8),
    hinge_x=(17.6, 19.865),      # blind hole from the frame's inner face (x ~17.8), 2.1 deep
    # cups on every wall (original Gamma only): U ring + D face, as in the RTE
    cup_z=(23.0, 63.3), cup_r_out=10.0, cup_r_in=8.0, cup_arm=4.0,
    cup_ring=2.0, cup_face=1.2, cup_recess=0.5,   # bore continues 0.5 mm into the wall
)

# Jan's variants of Gamma (October 2025, Tinkercad): the cups replaced by the
# RTE mounting plate (rte/narrow_server.py mount_insert) on all five walls;
# on the two front walls the plate is cut 3 mm shorter on the door side.
# "no-floor" also closes the floor opening with a 3 mm disc.
GAMMA_VARIANTS = {
    "R2_CryoStandaloneGamma": dict(cups=True),
    "RQB2-R2_CryoStandaloneGamma-jrl04": dict(inserts=True),
    "RQB2-R2_CryoStandaloneGamma-jrl04-nofloor": dict(inserts=True, floor_disc=True),
}
INSERT_DOOR_TRIM = 3.0
FLOOR_DISC = dict(r=21.0, centre=(0.0, 9.84), h=3.0)


def _wall_plane(y):
    """Plane in a back wall at y: local x = world x, local y = world z, normal -y."""
    return Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))


def _gamma_cup(g, zc):
    """Cup on the back wall (normal +y), as added solid and recess to cut."""
    ro, ri, top, y = g["cup_r_out"], g["cup_r_in"], zc + g["cup_arm"], g["inner_apothem"]
    cut_top = Pos(0, top + 50) * Rectangle(200, 100)
    outer = (Pos(0, zc) * Circle(ro) + Pos(0, (zc + top) / 2) * Rectangle(2 * ro, top - zc)) - cut_top
    inner = Pos(0, zc) * Circle(ri) + Pos(0, (zc + top + 5) / 2) * Rectangle(2 * ri, top + 5 - zc)
    ring = extrude(_wall_plane(y + 0.01) * (outer - inner), g["cup_ring"] + 0.01)
    face = extrude(_wall_plane(y - g["cup_ring"]) * outer, g["cup_face"])
    recess = extrude(_wall_plane(y + g["cup_recess"]) * (Pos(0, zc) * Circle(ri)),
                     g["cup_recess"] + 0.01)
    return ring + face, recess


def _snap_to_hexagon(d, snap, g, tol=0.03):
    """Move outline points that lie within tol of an outer or inner hexagon
    side exactly onto it. SketchUp left the floor and the wall outlines up to
    0.012 mm apart on the same face; nearly coincident faces mesh into leaky
    STLs. Returns a copy of the part data."""
    import copy
    import numpy as np
    d = copy.deepcopy(d)
    sx, sy, _ = d["size"]
    lines = []                                   # (unit normal, distance)
    for k in range(6):
        a = np.radians(30 + 60 * k)
        lines.append((np.array([np.cos(a), np.sin(a)]), g["corner_r"] * 0.8660254))
        lines.append((np.array([np.cos(a), np.sin(a)]), g["inner_apothem"]))
    for band in d["bands"]:
        for poly in band["polys"]:
            ring = poly["ext"]
            if "pts" not in ring:
                continue
            out = []
            for x, y in ring["pts"]:
                p = np.array([x * snap - sx / 2, y * snap - sy / 2])
                for n, dist in lines:
                    off = p @ n - dist
                    if abs(off) < tol:
                        p = p - off * n
                out.append([(p[0] + sx / 2) / snap, (p[1] + sy / 2) / snap])
            ring["pts"] = out
    return d


def gamma(prof, cups=False, inserts=False, floor_disc=False, g=GAMMA):
    d = _snap_to_hexagon(prof["R2_CryoStandaloneGamma"], prof["snap_mm"], g)
    sx, sy, _ = d["size"]
    body = Pos(-sx / 2, -sy / 2, 0) * build_part(d, prof["snap_mm"])
    x0, x1 = g["hinge_x"]
    for zc in g["hinge_z"]:
        for sgn in (1, -1):
            pin = Pos(sgn * (x0 + x1) / 2, g["hinge_y"], zc) * Rot(0, 90, 0) * \
                Cylinder(g["hinge_r"], x1 - x0)
            body -= pin
    for th in g["walls"]:
        rot = Rot(0, 0, th - 90)                # back wall (90 deg) -> this wall
        if cups:
            for zc in g["cup_z"]:
                add, recess = _gamma_cup(g, zc)
                body = body - rot * recess + rot * add
        if inserts:
            # mount_insert: back face on y = 0, growing +y; turn it to face -y
            # and put it on the back wall, then on this wall
            front = th in (-30, -150)
            ins_x = rot * Rot(0, 0, 180) * Pos(1, 0, 0)   # where the insert's +x end goes
            hi_is_front = ins_x.position.Y < 0
            trim = dict(trim_hi=INSERT_DOOR_TRIM) if front and hi_is_front else \
                dict(trim_lo=INSERT_DOOR_TRIM) if front else {}
            ins = Pos(0, g["inner_apothem"] + 0.01, 0) * Rot(0, 0, 180) * mount_insert(**trim)
            body += rot * ins
    if floor_disc:
        f = FLOOR_DISC
        body += Pos(*f["centre"], f["h"] / 2) * Cylinder(f["r"], f["h"])
    return body.clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", default=str(HERE / "output"))
    ap.add_argument("--only", help="comma-separated part names")
    a = ap.parse_args()
    prof = json.loads(PROFILES.read_text())
    parts = [("R2_CryoLid-Simple", lambda: lid(prof)),
             ("R2_ChandelierSingle", lambda: chandelier(prof)),
             ("RQB2-Cryostat-jrl01", lambda: jrl01(prof))]
    parts += [(n, lambda v=v: gamma(prof, **v)) for n, v in GAMMA_VARIANTS.items()]
    only = set(a.only.split(",")) if a.only else None
    for name, make in parts:
        if only and name not in only:
            continue
        part = make()
        vol = check_solid(part, name)
        print("%s: %.2f x %.2f x %.2f mm, volume %.0f mm3" % (name, *bbox_size(part), vol))
        export_all(part, f"{name}.parametric", a.outdir)


if __name__ == "__main__":
    main()
