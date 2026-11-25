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

All in [`3D Model/print/`](3D%20Model/print):

- **[`originals/`](3D%20Model/print/originals)**: the standard parts, the STL
  files the [assembly guide](https://rasqberry.org/01-3d-model/02-hardware-assembly-guide/)
  shows. What to print, how many and in which color:
  [what to print](https://rasqberry.org/01-3d-model/02-hardware-assembly-guide/#3-what-to-print).
- **[`generated/`](3D%20Model/print/generated)**: every part rebuilt from code
  ([`cad/`](3D%20Model/cad)), as STL and as 3MF with the filament colour, large
  parts also split in two (`.split-A` / `.split-B`), and print plates.
  **Not yet tested:** nobody has printed the whole set. Feedback is very welcome,
  in an [issue](https://github.com/JanLahmann/RasQberry-Two/issues).

If a lid is too loose or too tight on the RTE servers, adjust its fit in
[`cad/RTE/rte_lid.py`](3D%20Model/cad/RTE/rte_lid.py).

![Exploded parts view of RasQberry 2 model](artwork/RasQberry2exploded.png "Exploded view of RasQerry 2")

We hope you have as much fun building a model of the IBM Quantum System Two as we have had designing it!   
We very much welcome your feedback and suggestions for improvement.

