#!/usr/bin/env python3
"""Parametric rebuild of the RTE server lid (R2_NarrowServerSingleLid).

Rebuilds `3D Model/originals/RTE/R2_NarrowServerSingleLid.stl` (SketchUp).
A cap the size of the server's footprint with a skirt underneath that
slides into the socket at the top of the server (narrow_server.py,
socket_x / socket_y). The skirt is a 1 mm wall; the cap is hollow up to a
2 mm top plate.

Fit: the skirt is the socket minus `clearance` per side, separately for x
(long side) and y (short side). The original has 0.4 mm on both. Jan scales
the lid "by a few % in one direction" so it fits his printer: lowering one
clearance does the same without changing the cap. Example: 2 % on the short
side is about clearance y = 0.2.

Coordinates as narrow_server.py: centred on x = y = 0, placed on the
server (cap underside on the server's top edge, z = 93.3).

Usage:  python rte_lid.py [--outdir ROOT] [--clearance X,Y]
"""
import argparse
import sys
from pathlib import Path

from build123d import Axis, Plane, Polygon, chamfer, extrude

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rqb_params  # noqa: E402
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402
from narrow_server import PARAMS as SERVER  # noqa: E402

PARAMS = dict(
    width=rqb_params.RTE_WIDTH, depth=rqb_params.RTE_DEPTH,
    edge_chamfer=0.5,            # the four vertical edges (cap and skirt)
    top_chamfer=0.5,             # round the top face
    cap_h=8.7,                   # cap height (hollow up to the top plate)
    top_plate=2.0,
    skirt_h=6.85,                # reaches into the server's socket
    skirt_wall=1.0,
    clearance=(0.4, 0.4),        # skirt to socket, per side: (x, y)
    seat_z=rqb_params.BODY_HEIGHT,   # server top edge = cap underside
)


def rect(w, d, c=0.0):
    """Centred w x d rectangle with 45 deg corner chamfers c."""
    hw, hd = w / 2, d / 2
    if c <= 0:
        return Polygon((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd), align=None)
    return Polygon((-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
                   (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c),
                   align=None)


def build(p=PARAMS):
    z_seat = p["seat_z"]
    z_top = z_seat + p["cap_h"]
    sx = SERVER["socket_x"][1] - SERVER["socket_x"][0] - 2 * p["clearance"][0]
    sy = SERVER["socket_y"][1] - SERVER["socket_y"][0] - 2 * p["clearance"][1]
    w = p["skirt_wall"]
    pocket = rect(sx - 2 * w, sy - 2 * w)

    cap = extrude(Plane.XY.offset(z_seat) * rect(p["width"], p["depth"], p["edge_chamfer"]),
                  p["cap_h"], dir=(0, 0, 1))
    top_edges = cap.edges().filter_by_position(Axis.Z, z_top - 1e-3, z_top + 1e-3)
    cap = chamfer(top_edges, p["top_chamfer"])
    skirt = extrude(Plane.XY.offset(z_seat - p["skirt_h"]) * rect(sx, sy, p["edge_chamfer"]),
                    p["skirt_h"] + 0.01, dir=(0, 0, 1))
    hollow = extrude(Plane.XY.offset(z_seat - p["skirt_h"] - 0.01) * pocket,
                     p["skirt_h"] + p["cap_h"] - p["top_plate"] + 0.01, dir=(0, 0, 1))
    return ((cap + skirt) - hollow).clean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--clearance", help="skirt clearance per side, X,Y in mm (default 0.4,0.4)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    p = dict(PARAMS)
    if a.clearance:
        p["clearance"] = tuple(float(v) for v in a.clearance.split(","))
    part = build(p)
    vol = check_solid(part, "NarrowServerSingleLid")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "R2_NarrowServerSingleLid", root=a.outdir,
                formats=tuple(a.formats.split(",")))


if __name__ == "__main__":
    main()
