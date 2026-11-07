#!/usr/bin/env python3
"""Complete `3D Model/print/` and give every STL there a coloured 3MF.

1. Copies every original (../originals/) that has no rebuilt counterpart
   yet into print/, in the same folder and under the same name (an
   original that is a copy of a rebuilt part gets the rebuild, SAME_AS). Jan's
   modifications are all rebuilt; the *_repaired copies stay in originals/.
2. Writes <name>.3mf next to every STL in print/: one body, with the
   filament from the bill of materials as its material (FILAMENT below).
   RQB2-Cryostat-jrl01.3mf (two colours) is written by
   cryostat/cryostat_model.py and left alone.

Run it after the part scripts (see README). Needs trimesh to read the STLs.

Usage:  python build_print.py
"""
import shutil
from pathlib import Path

import trimesh

from rqb_cad import OUTPUT, write_3mf

ORIGINALS = Path(__file__).resolve().parent.parent / "originals"
JAN = "3D Model - modifications - Jan"
MULTICOLOUR = {"RQB2-Cryostat-jrl01"}
# originals that are byte-identical copies of a rebuilt part: use the rebuild
SAME_AS = {"cryostat/R2_NarrowServerSingleLid.stl": "RTE/R2_NarrowServerSingleLid.stl"}

# (test on the path inside print/, filament); the first match wins
FILAMENT = [
    (lambda p: "Chandelier" in p.name, "silk gold"),
    (lambda p: p.name in ("R2_NarrowServerSingleLid.stl", "R2_CryoLid-Simple.stl"), "transparent"),
    (lambda p: p.parts[0] == "floor", "white"),
    (lambda p: p.parts[0] == "wall", "matte black"),
    (lambda p: p.parts[0] in ("RTE", "cryostat"), "silk silver"),
]


def copy_missing():
    n = 0
    for src in sorted(ORIGINALS.rglob("*.stl")):
        rel = src.relative_to(ORIGINALS)
        if src.stem.endswith("_repaired") or rel.parts[0] == JAN:
            continue
        dst = OUTPUT / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            same = SAME_AS.get(rel.as_posix())
            shutil.copy2(OUTPUT / same if same else src, dst)
            print(f"  {'rebuilt ' + same if same else 'original'}  {rel}")
            n += 1
    return n


def filament(rel):
    return next(f for test, f in FILAMENT if test(rel))


def write_all_3mf():
    n = 0
    for stl in sorted(OUTPUT.rglob("*.stl")):
        if stl.stem in MULTICOLOUR:
            continue
        rel = stl.relative_to(OUTPUT)
        m = trimesh.load(stl, force="mesh")
        write_3mf(stl.with_name(stl.stem + ".3mf"),
                  [(stl.stem, filament(rel), (m.vertices.tolist(), m.faces.tolist()))])
        n += 1
    return n


def main():
    print(f"copied {copy_missing()} originals without a rebuild")
    print(f"wrote {write_all_3mf()} 3MF files")


if __name__ == "__main__":
    main()
