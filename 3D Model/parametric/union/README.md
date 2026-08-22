# Union — IBM modular cryogenic cell (parametric model)

A desk-top miniature of one cell of IBM's **Modular Quantum Cryogenic
Architecture** (announced 2026-08-19, photo-asset name "Union"): the
box-shaped aluminium "fridge" with pocketed doors that replaces the cylindrical
cryostat, designed to be coupled side-by-side into larger systems.

The model is a **self-contained cell**; print two (or more) and they couple
side-by-side with magnets in the plinth — the same "clunk" that joins the RTE
servers to the RasQberry cryostat.

![preview desk](preview_desk.png)

Sources, provenance and the deliberate deviations from IBM's material are
listed in [sources.md](sources.md). This is the first model built with the
code-CAD approach described in [../README.md](../README.md); the lessons
learned are in the "Building a NEW model" section there.

## Presets

One script, two scales. All numbers come from the real cell in metres
(`REAL` in `union_model.py`) times the preset scale; feature sizes are then
clamped to what a 0.4 mm nozzle can print.

| | `desk` | `showpiece` |
|---|---|---|
| scale | 1:23.5 (body height **93.3 mm** = every existing RasQberry body) | 1:15 |
| cell W × D × H (mm) | 46.7 × 76.4 × 93.3 | 73.3 × 120.0 × 146.5 |
| plinth W × D (mm) | 48.8 × 78.6, 7.2 thick, 4.2 mm casters | 76.7 × 123.3, 11.3 thick |
| door W × H × T (mm) | 35.6 × 77.6 × 4.85 | 55.7 × 122.1 × 7.33 |
| pockets | 3 × 6 front/back, 5 × 6 sides; 2.9 mm deep, 1.9 mm webs | 4.3 mm deep, 3.0 mm webs |
| fine detail | — (clamps, handle, hinges too small) | toggle clamps, pull handle, hinge barrels, recessed "IBM" on the processor can |
| chandelier plates (mm) | 30.6 → 13.2, pitch 7.5 | 48.0 → 20.7, pitch 11.7 |
| filament (solid volume) | body 61 + plinth 29 + door 9 + chandelier 4 cm³ | 234 + 112 + 35 + 11 cm³ |

`python3 union_model.py --preset desk|showpiece|all` prints a table of all
derived dimensions and feature toggles.

## Parts and printing

All parts are exported in print orientation (resting on z = 0), **no
supports needed**. Files: `output/Union_<preset>_<part>.stl / .step / .3mf`.

| Part | Colour | Print orientation | Notes |
|---|---|---|---|
| `body` | silver (Silk Silver like the cryostat) | upside down — top plate on the bed, open bottom up | posts, top plate, three fixed pocketed panels, flat door jambs on the front posts; magnet pockets + chandelier hole in the ceiling |
| `plinth` | black (Matte Black like the wall) | upside down — top face with the 1 mm registration lip on the bed, casters up | magnet pockets for the door (top face) and for coupling (left/right faces), LED pocket + wire channel |
| `door` | silver | flat, pocketed face up (back on the bed); showpiece must print face-up because of clamps/handle | magnet pockets in the top and bottom edges (horizontal holes when printed flat) |
| `chandelier` | gold (Silk Gold) + copper details | upside down — largest plate on the bed; bridges ≤ 15 mm between the corner rods, no supports | locating stub on top glues into the ceiling hole |

Multi-colour (Prusa MMU / Bambu AMS): `output/Union_<preset>_assembly.3mf`
contains every coloured body in assembled position (silver body + door, black
plinth, gold chandelier, copper mixing chamber + processor can, white "IBM"
inlay on the showpiece). In PrusaSlicer use *File → Import → Import STL/3MF…*,
answer **"Yes"** to *"Multi-part object detected — import as a single object
with multiple parts?"*, then assign extruders per part and split it into
objects (right-click → *Split → To objects*) to lay the parts flat. For
single-colour printers simply print the four `Union_<preset>_<part>.stl`
files; the copper/white details are part of the chandelier STL.

## Bill of materials (per cell)

- 8 × disc magnets **Ø3 × 2 mm** for the door: 2 in the door's top edge ↔ 2 in
  the body's ceiling, 2 in the door's bottom edge ↔ 2 in the plinth top.
- 4 × disc magnets **Ø5 × 2 mm** for coupling cells (2 in each plinth side
  face). Orient every cell the same way (left face N out, right face S out) so
  any right face attracts any left face. Pockets are Ø0.25 mm oversize and
  0.1 mm shallow; glue (CA) the magnets flush.
- Optional LED: a 5 mm LED or a single WS2812 on a ≤ 10 mm round board in the
  plinth's centre pocket (Ø10 × 3 mm), wire in the 3 × 3 mm channel out of the
  rear edge; the body is open at the bottom so the light shines up into the
  chandelier. `--no-led` removes pocket and channel.
- CA glue for the chandelier stub and (optionally) body ↔ plinth.

## Assembly

1. Press/glue the magnets (check polarity twice — a door that repels is a
   reprint of the plinth or the body).
2. Glue the chandelier's stub into the hole in the body's ceiling (largest
   plate up).
3. Set the body over the plinth's registration lip (0.15 mm clearance; glue
   if you want it permanent — the LED wire leaves through the channel under
   the rear panel).
4. Hang the door between the front posts: it sits on the plinth, the top
   and bottom magnets hold it, the flat jambs stop it from being pushed in.
5. Couple cells side by side; print more cells as IBM adds modules.

## Regenerating and validating

```bash
cd "3D Model/parametric"
python3 -m venv .venv-cad && .venv-cad/bin/pip install build123d trimesh manifold3d shapely rtree numpy networkx matplotlib
cd union
../.venv-cad/bin/python union_model.py --preset all     # -> output/*
../.venv-cad/bin/python validate_union.py               # CI-style mesh checks + model checks
../.venv-cad/bin/python render_preview.py               # preview_<preset>.png
```

`validate_union.py` checks every STL the way the repo's CI does (watertight,
consistent winding, no degenerate faces, exactly one body, rests on z = 0,
fits the bed) and then the model itself: assembled height, door magnet
pockets in door / ceiling / plinth line up, coupling pockets mirror
left ↔ right, chandelier ≥ 1 mm clear of door and panels, stub engaged.

Note on the CI analyzer (`.github/scripts/stl_analyzer.py`): it used to
estimate "holes" from the Euler characteristic even for watertight meshes and
therefore flagged every body with a loop (the chandelier truss, the showpiece
door's pull handle, the wall's vent grilles). The estimate is now only applied
to non-watertight meshes; all Union parts pass.

## Parameters worth playing with

Everything is at the top of `union_model.py`:

- `PRESETS` — add a scale (`scale=1/20`) or flip `detail`.
- `REAL` — the cell itself (`POST_R`, pocket grid, chandelier plates…).
- `PRINT` — nozzle-driven minimums, clearances, magnet sizes, LED pocket.
- `COLOURS` — the five MMU slots.
