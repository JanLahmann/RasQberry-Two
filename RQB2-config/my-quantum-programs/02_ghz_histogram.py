"""
Three entangled qubits (a GHZ state) on the Qiskit Aer simulator, with the
results saved as a bar chart.

Run it:  python3 02_ghz_histogram.py
Then open ghz_histogram.png (double-click it in the file manager).

Try this: change N to 5, or remove the qc.cx(...) line and compare the chart.
"""
from qiskit import QuantumCircuit, transpile
from qiskit.visualization import plot_histogram
from qiskit_aer import AerSimulator

N = 3

qc = QuantumCircuit(N)
qc.h(0)
for qubit in range(1, N):
    qc.cx(0, qubit)
qc.measure_all()
print(qc.draw())

simulator = AerSimulator()
counts = simulator.run(transpile(qc, simulator), shots=1000).result().get_counts()
print("Results:", counts)

figure = plot_histogram(counts, title=f"GHZ state with {N} qubits")
figure.savefig("ghz_histogram.png")
print("Chart saved as ghz_histogram.png")
