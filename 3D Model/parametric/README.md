# Parametric wall model (Base / Back / Lid)

This folder contains a parametric, code-based rebuild of the three wall
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
