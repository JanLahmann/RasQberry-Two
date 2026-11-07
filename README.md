# RasQberry-Two-3Dmodel
3D model of IBM Quantum System Two, to build a functional model of IBM Quantum System Two aka "the RasQberry project".

The model captures the spirit of the System Two design, adhering closely to size ratios of the real physical system, with a little artistic license to produce a model that is
easy to print, assemble and "operate".

The essence of the marketing models used in promotional videos has been captured by fitting the the "Room Temperature Electronics" (RTE) boxes with magnets to give that 
satisfying "clunk" connection to the main cryostat structure.

Credit for the bulk of the 3D design work goes to [Eric Jenney](https://github.com/ejog), with significant input from [Andy Stanford-Clark](https://github.com/andysc),  [Sascha Schefenacker](https://github.com/saschaschefenacker), and [Jan Lahmann](https://github.com/JanLahmann) with ideas and testing input from a whole army of other enthusiastic contributors at IBM.

![Assembled model of Quantum System Two](artwork/RasQberry2model.png "RasQberry 2 model")

There are quite a lot of pieces, but they're easy to print, without the need for supports, and the process is [well-documented](https://rasqberry.org/01-3d-model/02-hardware-assembly-guide/).

## Files

All in [`3D Model/`](3D%20Model):

- **[`print/`](3D%20Model/print)**: the files to print. Every part has an
  STL and a 3MF; the 3MF already has the filament colour. Large parts also
  come split in two (`.split-A` / `.split-B`) for smaller printers.
- **[`originals/`](3D%20Model/originals)**: the original SketchUp and
  Tinkercad files, unchanged, for reference.
- **[`cad/`](3D%20Model/cad)**: the code that generates `print/`.

What to print (folders in `print/`):

| Section | Parts |
|---|---|
| Wall | `R2_Wall-Base-jrl01-2` (`-no-floor` if you print without floor), `R2_Wall-Lid`, `R2_Wall-Back+13` (to mount a Raspberry Pi; `R2_Wall-Back-SolidForStaticModels` for a display model), `RQB2-WallPanel-jrl02-2` |
| RTE | 9x `RQB2-R2_NarrowServerSingle-jrl02`, 9x `R2_NarrowServerSingleLid` |
| Cryostat | `RQB2-R2_CryoStandaloneGamma-jrl04` (`-no-floor` …), 3x `R2_ChandelierSingle`, `R2_CryoLid-Simple`, `R2_NewDoor` |
| Floor | `R2_Floor-Tile1` … `Tile6s` |

If a lid is too loose or too tight on the RTE servers, adjust its fit in
[`cad/RTE/rte_lid.py`](3D%20Model/cad/RTE/rte_lid.py).

![Exploded parts view of RasQberry 2 model](artwork/RasQberry2exploded.png "Exploded view of RasQerry 2")

We hope you have as much fun building a model of the IBM Quantum System Two as we have had designing it!   
We very much welcome your feedback and suggestions for improvement.

