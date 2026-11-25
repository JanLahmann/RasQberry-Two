# 3D printing details

Background for [what to print](/01-3d-model/02-hardware-assembly-guide/#3-what-to-print).

## The standard parts

The STL files in [`print/originals`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/originals) are the parts the
assembly guide shows. On a bed smaller than about 250 mm, split the Wall parts in
your slicer ([how](/01-3d-model/02-hardware-assembly-guide/#3-gluing-all-the-pieces-together)).
The filament amounts in the bill of materials are PrusaSlicer's estimate for
these parts (Prusament PLA, 0.20 mm layers, without supports).

## The new parts (not yet tested)

[`print/generated`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated) has parts rebuilt from code
([`cad`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/cad)); the others are copied from the originals. Nobody has printed
the whole set yet, so the originals stay the standard. Feedback is very welcome:
[open an issue](https://github.com/JanLahmann/RasQberry-Two/issues) or
[become a tester](/testing/).

- **Formats:** STL and 3MF (with the filament color) for every part, STEP for
  nearly all.
- **Split parts** (`.split-A` / `.split-B`) for printers smaller than about 250 mm.
- **Print plates** ([`plates`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated/plates)): PrusaSlicer projects
  (2.9 or later) for the Prusa Core One, with grams and print time per bed; for
  another printer, choose it in PrusaSlicer and arrange. `-indx` files are for
  the Core One INDX tool changer.
- **Jan's variant:** the plates build a different set from the assembly guide:
  `R2_Wall-Base-jrl01-2`, `R2_Wall-Back+13`, a galaxy-black LED panel frame
  (`RQB2-WallPanel-jrl02-2`), the cryostat `RQB2-R2_CryoStandaloneGamma-jrl04`
  with 9 separate RTE servers, and floor plugs that join the floor to the wall
  and the cryostat. Only this set has `-no-floor` versions of the wall base and
  the cryostat.
- **The whole model** in color ([`complete`](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/print/generated/complete)), to
  see what goes where.
