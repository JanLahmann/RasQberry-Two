# Parametric (code-CAD) models

RasQberry parts rebuilt as code (build123d) from the SketchUp and Tinkercad
STLs, so they can be changed by editing numbers instead of meshes.

## Layout

The code and the generated files follow the folders of `3D Model/` on the
`3D-model` branch:

```
parametric/
  rqb_params.py   values shared by all parts (scale, body height, fits, export)
  rqb_cad.py      shared helpers (export, dovetail split, checks) and PARTS,
                  the table of where each part is written
  wall/           wall Base / Back / Lid (+ split), Jan's base variants, panel
  RTE/            narrow RTE server (jrl02)
  cryostat/       lid, chandelier, Gamma body, Jan's jrl01 and jrl04
  output/         generated STL / STEP / 3MF, same folders and file names
                  as the originals they replace:
    wall/  cryostat/  cryostat/Standalone Version/
    3D Model - modifications - Jan/October 2025/{wall,RTE,cryostat}/
    3D Model - modifications - Jan/October 2025 - no-floor/{wall,cryostat}/
```

Jan's modifications are built by the same scripts as the part they modify
(as variants), so a change to the base part carries over. Which file to
print follows Jan's rule from
[discussion #93](https://github.com/JanLahmann/RasQberry-Two/discussions/93):
take the file from `October 2025 - no-floor` if it exists (and you print
without floor), else from `October 2025`, else the standard one.

## Parts

- **[`wall/`](wall/README.md)** — Base / Back / Lid with a split version for
  small printers; `R2_Wall-Base-jrl01-2` (+ no-floor); `RQB2-WallPanel-jrl02-2`.
- **[`RTE/`](RTE/README.md)** — `RQB2-R2_NarrowServerSingle-jrl02`: 10 x 47
  hole grid in both side walls, cups and ribs inside, all values in one
  `PARAMS` dict.
- **[`cryostat/`](cryostat/README.md)** — `R2_CryoLid-Simple`,
  `R2_ChandelierSingle`, `R2_CryoStandaloneGamma`; Jan's
  `RQB2-Cryostat-jrl01` and `RQB2-R2_CryoStandaloneGamma-jrl04` (+ no-floor).

## Regenerating

```bash
cd wall && python3 wall_model.py && python3 wall_panel.py && cd ..
python3 RTE/narrow_server.py          # ~2 min
python3 cryostat/cryostat_model.py    # --only NAME,... for single parts
```

Every script writes to `output/` by default (`--outdir ROOT` writes the same
tree elsewhere).

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
out = Path(__file__).parent / "output"
out.mkdir(exist_ok=True)
stem = str(out / "my-part")
export_stl(body, stem + ".stl")
export_step(body, stem + ".step")
m = Mesher(); m.add_shape(body); m.write(stem + ".3mf")
print("volume", round(body.volume / 1000, 2), "cm3")
```

Conventions to keep: mm units; one script (or module) per part family, in the folder of that family;
add the part to `rqb_cad.PARTS` and export with `export_part()`;
parameter block at the top; commit the generated `output/` files together
with the script that produced them; add print orientation and assembly
notes to the README. Gotchas that cost us time on the wall: `extrude()`
follows the sketch face normal, so force polygon winding counter-clockwise
(see `ring_sketch()` in `wall/wall_model.py`), and `align=` matters on every
primitive - decide corner vs. centre alignment explicitly.
