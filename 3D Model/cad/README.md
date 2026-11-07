# Code-CAD models (build123d)

RasQberry parts rebuilt as code from the SketchUp and Tinkercad STLs, so
they can be changed by editing numbers instead of meshes. The scripts write
`3D Model/print/`.

## Layout of `3D Model/`

```
print/       what to print: STL + 3MF (with the filament colour) + STEP,
             per part folder (wall/ floor/ cryostat/ RTE/). Generated:
             rebuilt parts from cad/, the rest copied from originals/.
originals/   the SketchUp/Tinkercad STLs and Jan's modifications, untouched
             (*_repaired.stl: mesh repairs made by CI)
cad/         this code
  rqb_params.py    values shared by all parts (scale, body height, fits, export)
  rqb_cad.py       shared helpers (export, dovetail split, 3MF writer,
                   FILAMENTS) and PARTS, the table of where each part is written
  build_print.py   copies the not-yet-rebuilt originals into print/ and
                   writes a coloured 3MF for every STL there
  wall/ RTE/ cryostat/   one folder per part family
```

In `print/`, Jan's modifications sit next to the part they modify, and the
versions without floor end in `-no-floor` (in `originals/` they are in
`3D Model - modifications - Jan/October 2025[ - no-floor]/`).

## Parts

- **[`wall/`](wall/README.md)**: Base, Back, Back+13 and Lid, each also
  split for small printers. Jan's `R2_Wall-Base-jrl01-2` (+ no-floor) and
  `RQB2-WallPanel-jrl02-2`.
- **[`RTE/`](RTE/README.md)**: Jan's server `RQB2-R2_NarrowServerSingle-jrl02`
  and the lid `R2_NarrowServerSingleLid`, with the fit adjustable per axis.
- **[`cryostat/`](cryostat/README.md)**: `R2_CryoLid-Simple`,
  `R2_ChandelierSingle`, `R2_CryoStandaloneGamma`, `R2_NewDoor`; Jan's
  `RQB2-Cryostat-jrl01` (lid with chandeliers, two-colour 3MF) and
  `RQB2-R2_CryoStandaloneGamma-jrl04` (+ no-floor).

Not rebuilt yet (copied from `originals/`): floor tiles, screw, hex nut,
`R2_Wall-Back-SolidForStaticModels`, `R2_NarrowYCryoConjoined`, the octopus
screw, and the other standalone cryostat and server versions.

## 3MF colours

From the bill of materials (`FILAMENTS` in `rqb_cad.py`, assigned in
`build_print.py`): wall black (matte preferred), floor white / rock white,
cryostat and RTE silk silver, chandeliers silk gold, lids transparent.
A multi-colour 3MF (jrl01) is one object with one part per colour; each part
carries its filament name and an extruder number (PrusaSlicer's 3MF
metadata, also read by Bambu Studio and OrcaSlicer). Checked in PrusaSlicer
2.9: every 3MF loads as a manifold object, jrl01 with 4 parts.

Three copied originals have open edges in the SketchUp mesh itself (their
`_repaired` copies too): `R2_NarrowYCryoConjoined`, `R2_CryoStandaloneBeta`,
`R2_ServerStandalone`. Slicers repair them on load; a rebuild would fix them.

## Regenerating

```bash
pip install build123d trimesh lxml shapely numpy
cd "3D Model/cad"
(cd wall && python3 wall_model.py && python3 wall_panel.py)
(cd RTE && python3 narrow_server.py && python3 rte_lid.py)     # server ~2 min
(cd cryostat && python3 cryostat_model.py && python3 new_door.py)
python3 build_print.py                  # copies + 3MFs, always last
```

Each part script takes `--outdir ROOT` to write the same tree elsewhere.

## Building a NEW model with this approach

The pipeline above is written around rebuilding an existing STL. For a
brand-new part the measurement half (`extract_profiles.py` /
`wall_profiles.json`) falls away and the approach reduces to:

1. **Write the part as code** (build123d, mm units). No GUI modelling —
   the Python script is the source of truth and lives in git like normal
   code, so every design change is a reviewable diff and regeneration is
   deterministic.
2. **Put every design decision in a parameter block** at the top of the
   file: dimensions, hole positions, clearances, magnet/insert sizes,
   split positions. Nothing magic hidden in the geometry code.
3. **Export all formats in one run**: STL and 3MF for printing, STEP for
   anyone who wants to edit in Fusion 360 / FreeCAD / Onshape.
4. **Validate programmatically** (trimesh + manifold3d) instead of only
   eyeballing in a slicer: volumes, wall thicknesses, clearances between
   mating parts, "do split segments overlap", bounding boxes vs. print
   bed. For reusable machinery (dovetail split, carve-outs, export
   helper) crib from `wall/wall_model.py`.

Starter template for a new part:

```python
#!/usr/bin/env python3
"""RasQberry <part name> - parametric model. All dimensions in mm."""
from pathlib import Path
from build123d import *          # pip install build123d

# --- parameters -----------------------------------------------------------
LENGTH, WIDTH, WALL = 120.0, 40.0, 2.4
HOLE_D, HOLE_SPACING = 3.2, (58.0, 49.0)   # e.g. Raspberry Pi 4/5 pattern

# --- geometry --------------------------------------------------------------
body = Box(LENGTH, WIDTH, WALL, align=(Align.MIN, Align.MIN, Align.MIN))
for dx in (0, HOLE_SPACING[0]):
    for dy in (0, HOLE_SPACING[1]):
        body -= Pos(20 + dx, (WIDTH - HOLE_SPACING[1]) / 2 + dy, 0) * \
                Cylinder(HOLE_D / 2, 3 * WALL)

# --- export ----------------------------------------------------------------
out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)
stem = str(out / "my-part")
export_stl(body, stem + ".stl")
export_step(body, stem + ".step")
m = Mesher(); m.add_shape(body); m.write(stem + ".3mf")
print("volume", round(body.volume / 1000, 2), "cm3")
```

Conventions to keep: mm units; one script (or module) per part family, in the folder of that family;
add the part to `rqb_cad.PARTS` and export with `export_part()`;
parameter block at the top; commit the generated `print/` files together
with the script that produced them (run `build_print.py` for the 3MF); add print orientation and assembly
notes to the README. Gotchas that cost us time on the wall: `extrude()`
follows the sketch face normal, so force polygon winding counter-clockwise
(see `ring_sketch()` in `wall/wall_model.py`), and `align=` matters on every
primitive - decide corner vs. centre alignment explicitly.
