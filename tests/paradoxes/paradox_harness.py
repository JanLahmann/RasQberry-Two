"""
Recording harness for the Quantum Paradoxes notebook regression test (#181).

It is imported inside the notebook kernel (a cell prepended by the test) and:

* hooks qiskit_aer's AerBackend.run, which covers AerSimulator, the old
  QasmSimulator and the Aer simulator behind the qiskit_ibm_runtime fake
  backends, and records every circuit a notebook sends to a simulator;
* computes the circuit's EXACT classical outcome distribution (no shots) with a
  small density-matrix simulator that handles mid-circuit measurement, reset,
  classical conditions (c_if and if_test) and the backend's noise model;
* answers input() prompts from a scripted list.

One JSON line per event is appended to the output file. The module only uses
APIs that exist in both Qiskit 0.39 and Qiskit 2.x, so the same harness
recorded the reference values from the original notebooks.
"""

import json

import numpy as np
from qiskit import ClassicalRegister
from qiskit.quantum_info import DensityMatrix, Operator, SuperOp

_STATE = {"out": None, "answers": [], "depth": 0}

_P0 = Operator(np.array([[1, 0], [0, 0]], dtype=complex))
_P1 = Operator(np.array([[0, 0], [0, 1]], dtype=complex))
_RESET1 = Operator(np.array([[0, 1], [0, 0]], dtype=complex))
_SKIP = ("barrier", "delay", "snapshot")


def _emit(record):
    """Append one JSON record to the output file."""
    with open(_STATE["out"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _condition_true(condition, cmap, cval):
    """Evaluate a (register-or-clbit, value) condition on a classical value."""
    target, value = condition
    if isinstance(target, ClassicalRegister):
        reg = 0
        for i, bit in enumerate(target):
            if (cval >> cmap[bit]) & 1:
                reg |= 1 << i
        return reg == value
    return ((cval >> cmap[target]) & 1) == int(value)


class _Noise:
    """Read-only view of an Aer NoiseModel (local/default gate and readout errors)."""

    def __init__(self, model):
        self.local = getattr(model, "_local_quantum_errors", {}) or {}
        self.default = getattr(model, "_default_quantum_errors", {}) or {}
        self.ro_local = getattr(model, "_local_readout_errors", {}) or {}
        self.ro_default = getattr(model, "_default_readout_error", None)

    def gate_error(self, name, qubits):
        """Return the QuantumError applied after gate `name` on `qubits`, or None."""
        err = self.local.get(name, {}).get(tuple(qubits))
        return err if err is not None else self.default.get(name)

    def readout(self, qubit):
        """Return the readout confusion matrix P[true][recorded] for a qubit, or None."""
        err = self.ro_local.get((qubit,), self.ro_default)
        return None if err is None else np.array(err.probabilities)


def _merge(target, cval, rho):
    if abs(np.trace(rho.data)) < 1e-14:
        return
    target[cval] = target[cval] + rho if cval in target else rho


def _apply_op(op, qubits, clbits, states, noise):
    """Apply one (unconditional) operation to the classical->density-matrix ensemble."""
    name = op.name
    if name in _SKIP:
        return states
    if name == "measure":
        qubit, cbit = qubits[0], clbits[0]
        confusion = noise.readout(qubit) if noise else None
        new = {}
        for cval, rho in states.items():
            for bit, proj in ((0, _P0), (1, _P1)):
                branch = rho.evolve(proj, [qubit])
                for rec in (0, 1):
                    weight = (1.0 if rec == bit else 0.0) if confusion is None else confusion[bit][rec]
                    if weight > 0:
                        _merge(new, (cval & ~(1 << cbit)) | (rec << cbit), branch * weight)
        states = new
    elif name == "reset":
        qubit = qubits[0]
        states = {c: r.evolve(_P0, [qubit]) + r.evolve(_RESET1, [qubit]) for c, r in states.items()}
    else:
        try:
            unitary = Operator(op)
        except Exception:  # non-unitary composite (e.g. initialize): recurse
            unitary = None
        if unitary is not None:
            states = {c: r.evolve(unitary, qubits) for c, r in states.items()}
        else:
            if op.definition is None:
                raise RuntimeError("cannot simulate instruction " + name)
            body = op.definition
            qmap = {bq: qubits[i] for i, bq in enumerate(body.qubits)}
            cmap = {bc: clbits[i] for i, bc in enumerate(body.clbits)}
            return _run_block(body, qmap, cmap, states, noise)
    if noise is not None:
        err = noise.gate_error(name, qubits)
        if err is not None:
            channel = SuperOp(err.to_quantumchannel())
            states = {c: r.evolve(channel, qubits) for c, r in states.items()}
    return states


def _run_block(circuit, qmap, cmap, states, noise):
    """Run a circuit body; qmap/cmap map its bits to global indices."""
    for inst in circuit.data:
        op = inst.operation
        qubits = [qmap[q] for q in inst.qubits]
        clbits = [cmap[c] for c in inst.clbits]
        if op.name == "if_else":  # Qiskit >= 1.x control flow
            cond = op.condition
            true_states = {c: r for c, r in states.items() if _condition_true(cond, cmap, c)}
            rest = {c: r for c, r in states.items() if not _condition_true(cond, cmap, c)}
            for body, selected in ((op.blocks[0], true_states),
                                   (op.blocks[1] if len(op.blocks) > 1 else None, rest)):
                if body is None:
                    continue
                bq = {b: qmap[o] for b, o in zip(body.qubits, inst.qubits)}
                bc = {b: cmap[o] for b, o in zip(body.clbits, inst.clbits)}
                done = _run_block(body, bq, bc, selected, noise)
                selected.clear()
                selected.update(done)
            states = rest
            for cval, rho in true_states.items():
                _merge(states, cval, rho)
            continue
        cond = getattr(op, "condition", None)  # legacy c_if (Qiskit < 2)
        if cond is not None:
            plain = op.copy()
            plain.condition = None
            active = {c: r for c, r in states.items() if _condition_true(cond, cmap, c)}
            states = {c: r for c, r in states.items() if not _condition_true(cond, cmap, c)}
            for cval, rho in _apply_op(plain, qubits, clbits, active, noise).items():
                _merge(states, cval, rho)
            continue
        states = _apply_op(op, qubits, clbits, states, noise)
    return states


def exact_probs(circuit, noise_model=None):
    """
    Exact probability of every classical outcome of `circuit`.

    Args:
        circuit (QuantumCircuit): circuit as sent to the simulator.
        noise_model (NoiseModel): optional Aer noise model to include.

    Returns:
        dict: bitstring (clbit 0 rightmost, no spaces) -> probability.
    """
    noise = _Noise(noise_model) if noise_model is not None else None
    qmap = {q: i for i, q in enumerate(circuit.qubits)}
    cmap = {c: i for i, c in enumerate(circuit.clbits)}
    states = {0: DensityMatrix.from_label("0" * circuit.num_qubits)}
    states = _run_block(circuit, qmap, cmap, states, noise)
    width = circuit.num_clbits
    out = {}
    for cval, rho in states.items():
        prob = float(np.real(np.trace(rho.data)))
        if prob > 1e-12:
            out[format(cval, "0%db" % width) if width else ""] = round(prob, 10)
    return out


def install(out, answers):
    """
    Install the hooks inside a notebook kernel.

    Args:
        out (str): JSON-lines file to append records to.
        answers (list): scripted answers for input() prompts ("0" once exhausted).
    """
    from qiskit_aer.backends.aerbackend import AerBackend

    _STATE["out"] = out
    _STATE["answers"] = list(answers)
    original_run = AerBackend.run

    def run(self, circuits, *args, **kwargs):
        job = original_run(self, circuits, *args, **kwargs)
        if _STATE["depth"]:  # fake backend delegating to an inner AerSimulator
            return job
        _STATE["depth"] += 1
        try:
            circs = circuits if isinstance(circuits, (list, tuple)) else [circuits]
            try:
                noise_model = self.options.noise_model
            except Exception:
                noise_model = None
            for circ in circs:
                rec = {"kind": "run", "noisy": noise_model is not None,
                       "num_qubits": circ.num_qubits, "exact": exact_probs(circ)}
                if noise_model is not None:
                    rec["exact_noisy"] = exact_probs(circ, noise_model)
                _emit(rec)
        finally:
            _STATE["depth"] -= 1
        return job

    AerBackend.run = run

    try:
        kernel = get_ipython().kernel  # noqa: F821 - defined inside IPython

        def raw_input(prompt=""):
            answer = _STATE["answers"].pop(0) if _STATE["answers"] else "0"
            _emit({"kind": "input", "prompt": str(prompt), "answer": answer})
            return answer

        kernel.raw_input = raw_input
    except NameError:
        pass
