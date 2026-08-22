#!/usr/bin/env python3
"""Render PNG previews of the Union parts (matplotlib, no GPU needed).

Usage: python3 render_preview.py [--preset desk|showpiece|all] [--out DIR]
Reads output/Union_<preset>_assembly.3mf (coloured bodies, assembled) and the
per-part STLs, writes preview_<preset>.png next to them.
"""
import argparse
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).parent
OUT = HERE / "output"
COL = {"silver": (0.80, 0.80, 0.82), "black": (0.15, 0.15, 0.16), "gold": (0.85, 0.66, 0.15),
       "copper": (0.85, 0.52, 0.33), "white": (0.95, 0.95, 0.95)}


def shade(mesh, base, light=(0.4, -0.6, 0.7)):
    n = mesh.face_normals
    l = np.array(light) / np.linalg.norm(light)
    k = 0.45 + 0.55 * np.clip(n @ l, 0, 1)
    return np.clip(np.outer(k, base), 0, 1)


def fine(mesh, max_edge):
    """Subdivide big triangles so matplotlib's painter sort works out."""
    m = mesh.copy()
    try:
        v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=max_edge, max_iter=6)
        return trimesh.Trimesh(v, f, process=False)
    except Exception:
        return m


def draw(ax, meshes, elev=22, azim=-55, title=""):
    allv = np.vstack([m.vertices for m, _ in meshes])
    size = (allv.max(0) - allv.min(0)).max()
    # one collection for everything so faces of different parts sort against each other
    tris, cols = [], []
    for m, base in meshes:
        m = fine(m, size / 25)
        tris.append(m.vertices[m.faces]); cols.append(shade(m, base))
    pc = Poly3DCollection(np.vstack(tris), facecolors=np.vstack(cols),
                          edgecolors="none", linewidths=0, zsort="average", antialiased=False)
    ax.add_collection3d(pc)
    lo, hi = allv.min(0), allv.max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
    ax.set_title(title, fontsize=9)


def load_assembly(preset):
    scene = trimesh.load(OUT / f"Union_{preset}_assembly.3mf")
    meshes = []
    for name, geom in scene.geometry.items():
        colour = next((c for c in COL if c in name), None)
        if colour is not None:
            rgb = COL[colour]
        elif getattr(geom.visual, "face_colors", None) is not None:
            rgb = geom.visual.face_colors[0][:3] / 255.0
        else:
            rgb = (0.7, 0.7, 0.7)
        geom.metadata["name"] = name
        meshes.append((geom, np.array(rgb)))
    return meshes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="all")
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    presets = ["desk", "showpiece"] if a.preset == "all" else [a.preset]
    for preset in presets:
        if not (OUT / f"Union_{preset}_assembly.3mf").exists():
            print(f"no output for {preset}, skipping"); continue
        asm = load_assembly(preset)
        fig = plt.figure(figsize=(16, 9), dpi=110)
        draw(fig.add_subplot(2, 3, 1, projection="3d"), asm, 18, 130, f"{preset}: assembled, front-left (door + left side)")
        draw(fig.add_subplot(2, 3, 2, projection="3d"), asm, 18, -50, f"{preset}: assembled, back-right")
        interior = [(m, c) for m, c in asm if "door" not in m.metadata.get("name", "")]
        draw(fig.add_subplot(2, 3, 3, projection="3d"), interior, 8, 90, f"{preset}: door removed, looking in from the front")
        for i, part in enumerate(("body", "door", "chandelier")):
            m = trimesh.load(OUT / f"Union_{preset}_{part}.stl")
            draw(fig.add_subplot(2, 3, 4 + i, projection="3d"), [(m, np.array(COL["silver" if part != "chandelier" else "gold"]))],
                 25, 120 if part == "door" else -60, f"{preset}: {part} in print orientation")
        fig.tight_layout()
        path = Path(a.out) / f"preview_{preset}.png"
        fig.savefig(path); plt.close(fig)
        print("wrote", path)


if __name__ == "__main__":
    main()
