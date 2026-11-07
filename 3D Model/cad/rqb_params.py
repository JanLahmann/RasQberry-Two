"""Parameters shared by all RasQberry parametric models.

Only values that belong to the whole model live here. Dimensions of a single
part stay in that part's own PARAMS. Add a value here only once at least two
parts are known to share it (measured or decided), and say where it comes
from.

All dimensions in mm.
"""

# Scale applied to every exported part (1.0 = the original RasQberry size).
# Clearances scale with it; for large changes check the fits.
SCALE = 1.0

# Module grid: every body (RTE server, cryostat) is this tall.
BODY_HEIGHT = 93.3          # RTE NarrowServerSingle, cryostat bodies

# Footprint of one narrow RTE server; neighbouring parts are laid out on it.
RTE_WIDTH = 38.1
RTE_DEPTH = 23.25

# Fits (per side) for parts that slot together.
CLEARANCE = 0.15            # wall dovetail keys

# Dovetail (puzzle) keys used to split parts that are too big for the bed.
DOVETAIL = dict(key_depth=9.0, key_neck=7.0, key_end=12.0)

# Printer limits.
PRINT = dict(
    nozzle=0.4,
    bed=150.0,              # split target: every segment must fit this bed
)

# Mesh export (STL / 3MF). Linear tolerance in mm, angular in radians; the
# finer of the two wins. 0.35 rad gives ~20 segments on a small hole, which
# keeps hole grids (RTE side walls) at a few MB instead of ~25 MB.
EXPORT = dict(stl_tolerance=0.01, stl_angular_tolerance=0.35)
