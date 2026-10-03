"""
Qiskit meets the LEDs: run a Bell circuit once per column of the panel and
show every result as a column of light.

Run it:  rq_python 04_bell_on_leds.py

'00' lights the lower half of a column in blue, '11' the whole column in
purple. Each run gives a different random pattern, but there is never an
'01' or '10': the two qubits are entangled.
"""
import time

from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler
from rq_led_utils import clear_all_leds, get_pixels, matrix_size, set_xy

pixels = get_pixels(brightness=0.2)
width, height = matrix_size()

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

# One shot per column of the panel.
shots = StatevectorSampler().run([qc], shots=width).result()[0].data.meas.get_bitstrings()
print("Results, left to right:", " ".join(shots))

try:
    for x, bits in enumerate(shots):
        if bits == "11":
            color, rows = (160, 0, 255), height          # whole column purple
        else:
            color, rows = (0, 0, 255), height // 2       # lower half blue
        for y in range(height - rows, height):
            set_xy(pixels, x, y, color)
        pixels.show()
        time.sleep(0.1)
    time.sleep(15)
finally:
    clear_all_leds()
