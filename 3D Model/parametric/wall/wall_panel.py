#!/usr/bin/env python3
"""Parametric rebuild of the wall panel (jrl02-2 variant).

Rebuilds `3D Model/3D Model - modifications - Jan/October 2025/wall/
RQB2-WallPanel-jrl02-2.stl` (Tinkercad): a flat 0.6 mm plate with a narrower
tab along the top edge. Exact rebuild (the original is 28 triangles).

Usage:  python wall_panel.py [--outdir ROOT]   (default ../output, see rqb_cad.PARTS)
"""
import argparse
import sys
from pathlib import Path

from build123d import Polygon, extrude

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rqb_cad import bbox_size, check_solid, export_part  # noqa: E402

PARAMS = dict(
    width=240.5,        # main plate
    height=79.097,
    tab_width=236.696,  # centred tab along the top edge (1.902 mm inset per side)
    tab_height=11.903,
    thickness=0.6,
)


def build(p=PARAMS):
    w, h, tw, th = p["width"], p["height"], p["tab_width"], p["tab_height"]
    i = (w - tw) / 2
    outline = Polygon((0, 0), (w, 0), (w, h), (w - i, h), (w - i, h + th),
                      (i, h + th), (i, h), (0, h), align=None)
    return extrude(outline, p["thickness"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", help="output root (default ../output)")
    a = ap.parse_args()
    part = build()
    vol = check_solid(part, "WallPanel")
    print("size %.2f x %.2f x %.2f mm, volume %.0f mm3" % (*bbox_size(part), vol))
    export_part(part, "RQB2-WallPanel-jrl02-2", root=a.outdir)


if __name__ == "__main__":
    main()
