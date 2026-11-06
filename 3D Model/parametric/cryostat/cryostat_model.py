#!/usr/bin/env python3
"""Parametric rebuild of the cryostat lid and chandelier, and Jan's
lid-with-chandeliers assembly (RQB2-Cryostat-jrl01).

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

from build123d import Circle, Plane, Polygon, Pos, Rot, RegularPolygon, extrude

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from rqb_cad import bbox_size, check_solid, export_all  # noqa: E402
from wall_model import build_part, ring_sketch  # noqa: E402

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", default=str(HERE / "output"))
    a = ap.parse_args()
    prof = json.loads(PROFILES.read_text())
    for name, part in (("R2_CryoLid-Simple", lid(prof)),
                       ("R2_ChandelierSingle", chandelier(prof)),
                       ("RQB2-Cryostat-jrl01", jrl01(prof))):
        vol = check_solid(part, name)
        print("%s: %.2f x %.2f x %.2f mm, volume %.0f mm3" % (name, *bbox_size(part), vol))
        export_all(part, f"{name}.parametric", a.outdir)


if __name__ == "__main__":
    main()
