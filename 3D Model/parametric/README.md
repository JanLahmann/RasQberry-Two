# Parametric (code-CAD) models

This folder holds the RasQberry models that are written as code (build123d)
instead of drawn in a GUI:

- **the wall** (Base / Back / Lid) — a rebuild of the SketchUp originals with
  a split version for small printers, described below;
- **[`union/`](union/README.md) — IBM's modular cryogenic cell ("Union")**,
  the first model built from scratch with this approach (two scale presets,
  magnetic door, gold chandelier, multi-colour output);
- `rqb_cad.py` — the shared helper library both use (export to STL/STEP/3MF,
  multi-colour 3MF, dovetail split, rounded boxes, magnet pockets, checks).

Set-up for all of them (build123d is not in the default Python):

```bash
cd "3D Model/parametric"
python3 -m venv .venv-cad
.venv-cad/bin/pip install build123d trimesh manifold3d shapely rtree numpy networkx matplotlib
.venv-cad/bin/python wall_model.py            # or union/union_model.py
```

## The wall (Base / Back / Lid)

This is a parametric, code-based rebuild of the three wall
parts of the RasQberry Two 3D model:

| Part | Original STL (branch `3D-model`) | Size (mm) |
|---|---|---|
| Base | `3D Model/wall/R2_Wall-Base.stl` | 245.7 x 60.0 x 83.5 |
| Back | `3D Model/wall/R2_Wall-Back.stl` | 245.3 x 9.7 x 80.5 |
| Lid | `3D Model/wall/R2_Wall-Lid.stl` | 245.7 x 60.0 x 98.7 |

The originals were modelled in SketchUp and are only available as STL
meshes. This rebuild turns them into true CAD solids and addresses two
long-standing wishes:

1. **Editable formats.** Every part is exported as **STEP** (imports
   cleanly into Fusion 360, FreeCAD, Onshape, ...; recognized circles are
   true cylindrical faces, not 24-gons), **3MF** and **STL**.
   See the format discussion in
   [discussion #93](https://github.com/JanLahmann/RasQberry-Two/discussions/93).
2. **Split version for smaller printers.** At ~246 mm the wall does not
   fit many common print beds. Each part is additionally generated as two
   segments joined by printable dovetail (puzzle) keys; Base and Lid are
   cut on the middle facade seam (2 x ~123 mm), the Back at 97 mm — all
   segments fit a 150 mm bed. See "Split design" below.

## Files

- `extract_profiles.py` — measures the original STLs and writes
  `wall_profiles.json`. The wall parts are almost perfectly prismatic
  (stacks of constant cross-sections), so the mesh can be captured exactly
  as a list of "bands", each with its 2D contours. Rings whose vertices
  lie on a circle (within 0.05 mm) are stored as true circles.
- `wall_profiles.json` — the measured geometry (generated, committed for
  reproducibility).
- `wall_model.py` — rebuilds the three parts as B-rep solids from the
  measured profiles and applies the parametric split. All tunables are at
  the top of the file: cut positions, key positions/sizes, clearance.
- `rqb_cad.py` (parent folder) — shared helpers: `export_all`,
  `export_multicolour_3mf`, `split_part` / `trapezoid_prism` (the dovetail
  machinery, now taking cuts/keys/carve-outs as arguments), `rounded_box`,
  `magnet_pocket`, `check_solid`.
- `output/` — generated STL / STEP / 3MF files, one-piece
  (`*.parametric.*`) and split (`*.split-A.*`, `*.split-B.*`).

## Regenerating

```bash
pip install build123d trimesh shapely rtree numpy

# fetch the original STLs (only needed to re-run the measurement)
mkdir -p /tmp/wall-src
for f in R2_Wall-Base R2_Wall-Back R2_Wall-Lid; do
  git show "origin/3D-model:3D Model/wall/$f.stl" > "/tmp/wall-src/$f.stl"
done
python3 extract_profiles.py /tmp/wall-src   # -> wall_profiles.json
python3 wall_model.py                       # -> output/*
```

## Fidelity

The rebuild was validated against the original meshes with boolean
operations (volume of the symmetric difference):

| Part | Volume rebuilt vs. original | Symmetric difference |
|---|---|---|
| Base | 106.37 vs. 106.37 cm³ | 0.17 % |
| Back | 73.06 vs. 73.06 cm³ | 0.38 % |
| Lid | 61.25 vs. 61.25 cm³ | 0.24 % |

The remaining difference is dominated by the louvre blades of the two
round vent grilles in the back panel (the only notably non-prismatic
feature; they are reproduced from the band mid-lines, which straightens
the blade slope slightly). All other features — floor openings, ribs,
alignment posts, lid pegs, screw bosses, the seam grooves on the lid's top
face — are reproduced exactly.

For the split versions: the segments do not overlap, no key material lies
outside the original part's volume, and the total clearance gap is
17-50 mm³ per part (0.15 mm per side around each key).

## Split design

**Base and Lid are cut on a pre-existing seam.** The wall facade has five
vertical seam lines (the lid pegs, continued by matching grooves on the
lid's top face) at x = 43.86 / 82.86 / 122.86 / 162.86 / 201.86. The cut
runs through the centre of the middle seam (x = 122.86, which is also the
exact centre of the part), so the visible joint disappears into the seam:

- on the **Base** the cut passes through the pre-existing gap in the front
  lip (x = 121.26-124.46) — no new line on the facade;
- on the **Lid** the free-hanging front peg is kept in one piece (assigned
  wholly to segment A via a stepped cut) and the joint follows the seam
  line; on the top face the cut runs between the decorative seam grooves.

Interior faces are allowed to be pragmatic: the cut crosses the base's
circular floor opening and halves the middle rib and the lid's centre
post lengthwise — the halved rib and post still mate with each other
after assembly, and none of this is visible from the outside.

The **Back** keeps its cut at x = 97: at 122.86 its screw bosses
(x = 123.8-129.8) are in the way, its rear face carries no seam lines,
and staggering the back joint against the base/lid joint stiffens the
assembled wall.

Segment widths: Base/Lid 2 x ~123 mm, Back 97 + 148 mm — everything fits
a 150 mm bed. Keys sit in:

- **Base**: bottom plate (3 mm), keys at y = 9/45 (clearing the circular
  floor opening, centre y 27.3 / r 11, that the seam cut passes through)
- **Back**: main panel (4 mm), keys at z = 15/40/65
- **Lid**: top plate (z = 96.97-98.32, the only solid cross-plate at the
  cut; the keys stop below the decorative seam grooves so the visible top
  face stays clean)

Segments assemble by dropping the dovetails in perpendicular to the plate
and are intended to be glued (the lid's 1.35 mm key plate in particular
relies on glue). The joints of Base/Lid vs. Back end up laterally offset
in the assembled wall, which stiffens the result. Print orientation is
the same as for the original parts; no supports needed.

## Notes / possible next steps

- `R2_Wall-Back+13.stl` (the variant used with the current wall panel) has
  the same footprint as `R2_Wall-Back.stl`; it can be processed with the
  same two scripts by pointing `extract_profiles.py` at it.
- More than one cut is supported (`CUTS` takes a list of positions), e.g.
  for three ~82 mm segments on very small printers — each additional cut
  position must be chosen in a feature-free zone as above.
- The measured-profile approach also makes targeted modifications easy
  (e.g. display cutouts, #224, or heat-set insert bosses from
  discussion #93): edit `wall_model.py` to add/subtract features on top of
  the rebuilt solids.

## Building a NEW model with this approach

The pipeline above is written around rebuilding an existing STL. For a
brand-new part the measurement half (`extract_profiles.py` /
`wall_profiles.json`) falls away. The Union cell (`union/`) is the first
model built this way; what worked, in the order you would do it again:

1. **Write the part as code** (build123d, algebra mode). No GUI modelling —
   the Python script is the source of truth and lives in git like normal
   code, so every design change is a reviewable diff and regeneration is
   deterministic.
2. **Author in real-world units and scale down.** Put the real object in a
   `REAL = {...}` dict (metres, straight from photos / data sheets / whatever
   you could decode) and a `PRESETS` dict with the scales you want (`desk`
   = 93.3 mm body height, the RasQberry style constant; `showpiece` = 1:15).
   Nothing magic hidden in the geometry code.
3. **Derive feature toggles from printability, not by hand.** A `PRINT` dict
   (0.4 mm nozzle: min wall 1.0, min web 1.0, min free-standing detail 0.6,
   magnet sizes, clearances) and a `Dims` class that computes every mm
   number *and* decides which details exist at this scale (clamps, handles,
   text…). Print the derived table at run time — it is the first thing to
   look at when something is off.
4. **One part = one closed solid, exported in print orientation** (resting
   on z = 0), plus one **assembled, coloured 3MF** of all parts for
   multi-material printers. Hand build123d's `Mesher` the bare `Solid`
   (`rqb_cad.export_multicolour_3mf` does this) — handing it a `Part`
   silently drops names and colours.
5. **Export all formats in one run**: STL and 3MF for printing, STEP for
   anyone who wants to edit in Fusion 360 / FreeCAD / Onshape.
6. **Validate programmatically** with a `validate_<model>.py` next to the
   model (trimesh): the CI checks (watertight, winding, no degenerate faces,
   one body per STL, fits the bed) plus model checks (mating magnet pockets
   line up, clearances, assembled height). Use a manifest JSON written by
   the model script so the validator never re-derives numbers.
7. **Render previews** (`render_preview.py`, matplotlib, no GPU) and commit
   the PNGs — they go into the README and the website, and they catch
   "the door faces the wrong way" in seconds.
8. **Per-model subfolder** with `README.md` (presets, parts, print
   orientation, BOM, assembly), `sources.md` (provenance and deliberate
   deviations, licences) and `output/`. Commit the generated `output/` files
   together with the script that produced them.

Gotchas that cost us time:

- `extrude()` follows the sketch face normal — force polygon winding
  counter-clockwise (`rqb_cad.ccw_polygon`); `align=` matters on every
  primitive — decide corner vs. centre alignment explicitly.
- matplotlib's `azim=-90` looks from −y: label your preview views by what
  they show, not by what you meant.
- Spheres tessellate into zero-area triangles at the poles; the CI analyzer
  rejects those. Use short cylinders for knobs.
- Two perpendicular cylinders of EQUAL radius whose axes intersect touch
  tangentially — OCCT builds an invalid B-rep from the union. Make one of
  them 10–15 % fatter (door handle stand-offs, wire bails).
- Round posts intersect flat doors behind the face — give the posts a flat
  jamb instead of notching the door (no feather edges).
- build123d's `Shape.is_valid` is a property in 0.11 (was a method).
- The CI analyzer's "hole" count came from the Euler characteristic, which
  also drops for watertight bodies with loops (trusses, handles, grilles);
  it now only runs on non-watertight meshes. If an STL is flagged, check
  `is_watertight` first.
