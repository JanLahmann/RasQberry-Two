# Cryostat: lid, chandelier, body, door (parametric rebuild)

`cryostat_model.py` and `new_door.py` rebuild the cryostat parts from the
SketchUp and Tinkercad STLs in `originals/`. Each part is written to
`print/cryostat/` under its original file name; Jan's versions sit next to the
part they modify:

| Output | Original | Deviation |
|---|---|---|
| `R2_CryoLid-Simple.*` | `originals/cryostat/R2_CryoLid-Simple.stl` | ≤ 0.03 mm |
| `R2_ChandelierSingle.*` | `originals/cryostat/R2_ChandelierSingle.stl` | ≤ 0.05 mm |
| `RQB2-Cryostat-jrl01.*` | `originals/3D Model - modifications - Jan/October 2025/cryostat/RQB2-Cryostat-jrl01.stl` | ≤ 0.34 mm (see below) |
| `R2_CryoStandaloneGamma.*` | `originals/cryostat/Standalone Version/R2_CryoStandaloneGamma.stl` | shell ≤ 0.05 mm (p99), cups ≤ 1.8 mm (centred, see below) |
| `R2_CryoStandaloneBeta.*` | `originals/cryostat/Standalone Version/R2_CryoStandaloneBeta.stl` | shell ≤ 0.02 mm (p99), cups ≤ 1.7 mm (centred, as Gamma) |
| `RQB2-R2_CryoStandaloneGamma-jrl04.*` | `… modifications - Jan/October 2025/cryostat/RQB2-R2_CryoStandaloneGamma-jrl04.stl` | ≤ 0.65 mm (inserts centred) |
| `RQB2-R2_CryoStandaloneGamma-jrl04-no-floor.*` | `… October 2025 - no-floor/cryostat/RQB2-R2_CryoStandaloneGamma-jrl04.stl` | ≤ 0.65 mm |
| `R2_NewDoor.*` (`new_door.py`) | `originals/cryostat/R2_NewDoor.stl` | ≤ 0.05 mm |
| `R2_ScrewOctopusAlignment2.*` (`screw_octopus.py`) | `originals/cryostat/R2_ScrewOctopusAlignment2.stl` | ≤ 0.24 mm (p99 0.13) |
| `R2_NarrowYCryoConjoined.*` (`narrow_y_conjoined.py`) | `originals/cryostat/R2_NarrowYCryoConjoined.stl` | p99 0.34 mm, max 1.0 mm (see below) |

```bash
cd "3D Model/cad/cryostat"
python3 extract_cryo_profiles.py <dir with the original STLs>  # only to re-measure
python3 cryostat_model.py                                      # -> print/cryostat/
python3 new_door.py
python3 screw_octopus.py
python3 narrow_y_conjoined.py                                  # ~3 min
```

- **Lid:** hexagonal, 76.2 x 66.0 x 20.7 mm, with three sockets on the
  underside (1 mm hexagonal recess + Ø 8 mm hole, 7.35 mm deep). Captured as
  stacked cross-sections, like the wall.
- **Chandelier:** stem (z 0–14.7), six-armed column, four hexagonal plates
  (17.47 mm across flats, 1.5 mm thick), Ø 3.98 mm hole through the middle.
  The stem and column outlines are measured; plates and hole are numbers in
  `CHANDELIER`.
- **jrl01 (Jan's Tinkercad assembly):** the lid turned over (sockets up) with
  three chandeliers hanging upside down from it; each top plate stands in a
  socket recess with 0.1 mm overlap so the parts fuse. One print, lid down.
  Its 3MF has two colours: the lid transparent, the chandeliers silk gold.
- **Door (`new_door.py`):** front panel (38.1 x 93.3 mm, 2.4 mm thick,
  60 deg side bevels, recessed field between two grooves), two rails at the
  back with rounded tops and blind pin holes (the hinge, at z 9.8 and 74.8),
  and a 3 mm foot that reaches under the cryostat. All numbers in `PARAMS`.
  Jan placed the chandeliers by hand, up to 0.27 mm off the socket centres;
  the rebuild puts them exactly on the centres (hence the 0.34 mm).

![Jan's file vs rebuild](compare_jrl01.png)

### Gamma (standalone cryostat body) and Jan's jrl04

- **Shell:** hexagonal, 76.2 x 66.0 x 93.3 mm, five walls, open front with a
  door frame, 3 mm floor with a front notch and a hexagonal opening with three
  tabs, V-grooves round the whole outside at z 2.5 and 85.3, lid socket at the
  top. Captured as stacked cross-sections; the grooves in 0.1 mm layers. The
  SketchUp mesh is broken between z 2.0 and 2.5, so those layers are taken
  from the (repaired) Gamma body in Jan's Tinkercad export.
- **Hinge holes:** Ø 3.18 mm (1/8"), 2.1 mm deep, in each door-frame post at
  z 9.8 and 74.8.
- **Cups** (original only): two per wall, U ring R 10 / R 8 with a D face, the
  bore continuing 0.5 mm into the wall. In the SketchUp file the front-wall
  cups sat up to 0.8 mm off centre and 0.2 mm low; here all are centred.
- **jrl04 (Jan):** the cups replaced by the RTE mounting plate
  (`RTE/narrow_server.py`, `mount_insert`) on all five walls; on the two
  front walls it is cut 3 mm shorter on the door side. Centred on the walls
  (Jan's placement was up to 0.11 mm off). The no-floor version closes the
  floor opening with a Ø 42 x 3 mm disc.

![Jan's jrl04 vs rebuild](compare_gamma_jrl04.png)

- **Beta:** the Gamma body with cups on three walls only: the back and the
  two front walls (`cup_walls` in `GAMMA_VARIANTS`). The SketchUp file is an
  open mesh (10 open edges); the rebuild is closed.

### Octopus alignment screw (`screw_octopus.py`)

A hexagonal hub (31.7 mm across the flats) with three 36 mm arms at 120 deg
(a 1 mm strip with two outward-leaning rails), a smaller hexagon up to
z 8.5 and a threaded tube up to z 15, Ø 19.9 mm hole through. The thread is
drawn as in SketchUp: a circle (r 12.28) 0.70 mm off the axis, turning once
per 2 mm (one start, anticlockwise upwards). Centred on the hub (the
original sits at x −39.96, y −6.31). All numbers in `PARAMS`.

### Conjoined cryostat (`narrow_y_conjoined.py`)

`R2_NarrowYCryoConjoined` (157 x 136 x 93.3 mm; in SketchUp 568k triangles
in 113 overlapping bodies, not watertight) is the Gamma body without cups,
with a double server (`RTE/server_standalone.py`) as an arm on the back wall
and on both front walls, like a Y. Each arm stands 0.2 mm off the wall
(filled) and opens into the cryostat: the arm's inner end wall and the
cryostat wall are cut away over the server cavity width. On the two front
walls the opening stops 10 mm from the wall centre on the door side, so the
door-frame post and the wall behind it stay. Each arm keeps its two cups on
the outer end wall. Centred on the cryostat (door towards -y).

Comparison (surface samples both ways, the original's hidden inner faces
left out): median 0.002 mm, 99 % within 0.34 mm; up to 1.0 mm at the
door-frame posts where the front arms join and at the floor edge at
z ≈ 2 (where the SketchUp Gamma mesh is broken, see Gamma above).

The STL (840k triangles, 42 MB) needs one clean-up step: where an arm meets
the cryostat's 0.1 mm groove layers, OCCT meshes slivers narrower than
0.1 µm, which leave a few open edges. The script merges vertices closer
than 0.1 µm and drops the collapsed triangles, so the STL is closed (the
solid itself is valid).
