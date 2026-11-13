# Floor tiles (parametric rebuild)

`floor_model.py` rebuilds the six floor tiles, the two magnet versions and
the whole floor in one piece:

| Part | Original | max deviation |
|---|---|---|
| `R2_Floor-Tile1` … `Tile4` | `originals/floor/` | ≤ 0.65 mm (tile number), else ≤ 0.35 |
| `R2_Floor-Tile5`, `Tile6s` | `originals/floor/` | ≤ 0.47 mm; Tile6s sign 1.15 mm |
| `R2_Floor-Tile1Mag`, `Tile2Mag` | `originals/floor/Sign Magnet Indent Version/` | ≤ 0.61 mm |
| `R2_Floor-all` | `originals/floor/R2_Floor-all.stl` | the six tiles fused |

Medians are 0.000 mm; the larger values are single spots: inside faces of
the original where SketchUp left the tile number as a separate body, and
the small relief sign under Tile6s, rebuilt as 0.1 mm slabs. All nine are
closed solids (the original `R2_Floor-all` is not, and sits 0.04 mm lower
than its own tiles).

## What a tile is

130 x 130 x 10 mm; the floor is 2 x 3 tiles (x 0..260, y 0..390).

- a 3 mm top plate, its top edge chamfered 0.75 mm at 45 deg, so two tiles
  meet in a small V;
- a 3 mm skirt underneath, open where the parts above need room;
- Ø 3.2 holes through the skirt where two tiles meet, for alignment pins
  (pieces of filament or 3 mm dowels);
- the tile number, mirrored, 2 mm raised under the plate;
- Tile5 / Tile6s (front row): V-grooves dividing the top into four
  squares, a hexagonal hole and half of the Ø 22 cable hole they share;
  Tile6s carries a small relief sign underneath;
- Tile1Mag / Tile2Mag: three Ø 16 x 1 mm magnet pockets under the plate.

## How it is built

The numbers (plate, chamfer, groove, pin and magnet sizes, cable hole) are
in `PARAMS`; the grooves and the cable hole per tile in `TILES`. The
outlines that are not simple numbers (plate with its key notches, skirt,
tile numbers, the sign) were measured from the originals by
`extract_floor.py` into `floor_profiles.json`. Coordinates within 0.05 mm
of a tile edge are snapped onto it (SketchUp left some seam walls 0.025 mm
off, which would make the fused floor touch only along a line).

The tiles keep the original's frame (top at z = 0); `R2_Floor-all`
stands on z = 0.

```bash
python3 floor_model.py                 # all, ~30 s
python3 floor_model.py --only Tile5    # one tile
python3 extract_floor.py               # only to re-measure the originals
```
