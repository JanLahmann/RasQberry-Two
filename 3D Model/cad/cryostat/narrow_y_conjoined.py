#!/usr/bin/env python3
"""Parametric rebuild of the conjoined cryostat (R2_NarrowYCryoConjoined).

Rebuilds `3D Model/originals/cryostat/R2_NarrowYCryoConjoined.stl`
(SketchUp, 568k triangles in 113 overlapping bodies): the standalone
cryostat body (Gamma, cryostat_model.py) with a pair of servers
(RTE/server_standalone.py) as an arm on three of its walls - the back wall
and the two front walls - like a Y. Each arm opens into the cryostat: the
cryostat wall and the arm's inner end wall are cut away over the server
cavity width (on the two front walls only up to the door-frame post, 10 mm
from the wall centre). The cryostat has no cups; each arm has two on its
outer end wall.

Coordinates: centred on the cryostat (hexagon centre at x = y = 0, door
opening towards -y), standing on z = 0.

Usage:  python narrow_y_conjoined.py [--outdir ROOT]
"""
import argparse
import json
import sys
from pathlib import Path

from build123d import Pos, Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "RTE"))
from rqb_cad import bbox_size, check_solid, export_part, part_path  # noqa: E402
from cryostat_model import GAMMA, PROFILES, gamma  # noqa: E402
from narrow_server import _box, variant  # noqa: E402
from server_standalone import PARAMS as PAIR, build_pair  # noqa: E402

PARAMS = dict(
    arm_walls=(90, -30, -150),   # outward normals of the walls carrying an arm
    arm_gap=0.2,                 # between the cryostat's outer face and the arm (filled)
    # on the two front walls the opening stops this far from the wall centre
    # on the door side, so the door-frame post and the wall behind it stay
    door_side_open=10.0,
)


def build(p=PARAMS):
    prof = json.loads(PROFILES.read_text())
    body = gamma(prof)                               # no cups: none in the original
    s = variant("original")
    cx, H, fl = s["cavity_x"], s["height"], s["floor"]
    apothem = GAMMA["corner_r"] * 3 ** 0.5 / 2        # outer face of a wall
    pair = build_pair(open_end=True)
    arm_len = 2 * s["depth"] + PAIR["gap"]
    g, fx = p["arm_gap"], PAIR["filler_x"]
    for th in p["arm_walls"]:
        rot = Rot(0, 0, th - 90)                     # back wall (90 deg) -> this wall
        x0, x1 = cx
        if th == -150:                               # door side is local -x
            x0 = -p["door_side_open"]
        elif th == -30:                              # door side is local +x
            x1 = p["door_side_open"]
        # the wall only; the door-frame posts in front of it stay
        wall = _box(x0, x1, GAMMA["inner_apothem"] - 0.01, apothem + g + 1, fl, H + 1)
        body -= rot * wall
        opening = _box(cx[0], cx[1], apothem - 1, apothem + g + 1, fl, H + 1)
        filler = _box(-fx, fx, apothem - 0.01, apothem + g + 0.01, 0, H) - opening
        arm = Pos(0, apothem + g + arm_len / 2, 0) * pair
        body += rot * (arm + filler)
    return body.clean()


def close_slivers(stl_path):
    """Close the STL where OCCT meshed zero-width slivers.

    Where an arm's side wall meets the cryostat's groove layers (0.1 mm
    bands) at the door frame, the cut leaves faces narrower than 0.1 um. The
    solid is valid, but its STL then has a few open edges there. Merging
    vertices closer than 0.1 um and dropping the triangles that collapse
    closes it; nothing moves by more than 0.1 um. Returns the number of open
    edges left."""
    import trimesh
    from trimesh.grouping import group_rows
    m = trimesh.load(stl_path, process=False)
    m.merge_vertices(digits_vertex=4)
    f = m.faces
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    m = trimesh.Trimesh(m.vertices, f[keep], process=False)
    m.export(stl_path)
    return len(group_rows(m.edges_sorted, require_count=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../../print)")
    ap.add_argument("--formats", default="stl,step")
    a = ap.parse_args()
    part = build()
    vol = check_solid(part, "NarrowYCryoConjoined")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "R2_NarrowYCryoConjoined", root=a.outdir, formats=tuple(a.formats.split(",")))
    if "stl" in a.formats:
        left = close_slivers(part_path("R2_NarrowYCryoConjoined", root=a.outdir).with_suffix(".stl"))
        print("  closed the slivers in the STL; open edges left: %d" % left)


if __name__ == "__main__":
    main()
