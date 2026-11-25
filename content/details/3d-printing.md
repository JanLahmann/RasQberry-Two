# 3D printing details

Background for [what to print](/01-3d-model/02-hardware-assembly-guide/#3-what-to-print).

## The standard parts

The STL files in [`print/originals`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/originals) are the parts the
assembly guide shows. They print without supports. On a bed smaller than about
250 mm, split the Wall parts in your slicer
([how](/01-3d-model/02-hardware-assembly-guide/#3-gluing-all-the-pieces-together)).

## The new parts (not yet tested)

[`print/generated`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated) has every part rebuilt from code
([`cad`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/cad)). Nobody has printed the whole set yet; until then the
originals stay the standard. Feedback is very welcome:
[open an issue](https://github.com/JanLahmann/RasQberry-Two/issues) or
[become a tester](/testing/).

- **STL, 3MF and STEP** for each part; the 3MF already has the filament color.
- **Split parts** (`.split-A` / `.split-B`) for printers smaller than about 250 mm.
- **Without floor:** `-no-floor` versions of the wall base and the cryostat, without
  the holes for the floor plugs.
- **Floor plugs:** `R2_Floor-CryoPlug` and `R2_Floor-WallPlug` join the floor
  to the cryostat and the wall.
- **Print plates** ([`plates`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated/plates)): PrusaSlicer projects
  (2.9 or later), one per filament color, with grams and print time per bed. Made
  for the Prusa Core One; for another printer, choose it in PrusaSlicer and
  arrange. `-indx` files are for the Core One INDX tool changer.
- **The whole model** in color ([`complete`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated/complete)), to
  see what goes where.
