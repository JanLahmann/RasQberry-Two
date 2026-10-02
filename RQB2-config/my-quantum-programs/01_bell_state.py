"""
Your first quantum program: a Bell state, simulated on this Raspberry Pi.

Run it:  python3 01_bell_state.py   (in a terminal)
         or open it in Thonny and press Run.

No IBM Quantum account is needed: the circuit runs on a local simulator.
"""
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

# Two qubits: a Hadamard gate puts qubit 0 into superposition, and a CNOT gate
# entangles qubit 1 with it.
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()
print(qc.draw())

# Run the circuit 1000 times ("shots") on the built-in simulator.
result = StatevectorSampler().run([qc], shots=1000).result()
counts = result[0].data.meas.get_counts()

# About half the shots give '00' and half '11', but never '01' or '10':
# the two qubits always agree. That is entanglement.
print("Results:", counts)
