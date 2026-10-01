"""
The off-Pi install of the Qiskit compatibility workflow must mirror the image's:
it may leave out only the Pi-only hardware packages, never a Qiskit package.
(Runs without Qiskit.)
"""

import compat_ci


def test_filter_matches_requirements_file():
    kept, excluded = compat_ci.filtered_requirements()
    # every Pi-only name is still in the file - otherwise the filter list rots
    assert sorted(excluded) == sorted(compat_ci.PI_ONLY), (
        "PI_ONLY lists packages no longer in qiskit-requirements.txt (or misses some): "
        f"{sorted(set(compat_ci.PI_ONLY) ^ set(excluded))}")
    names = {compat_ci.requirement_name(line) for line in kept}
    assert not any(n.startswith("qiskit") for n in compat_ci.PI_ONLY)
    for required in ("qiskit-ibm-runtime", "qiskit-aer", "qiskit-algorithms"):
        assert required in names


def test_requirement_name_parsing():
    assert compat_ci.requirement_name("notebook<7  # comment") == "notebook"
    assert compat_ci.requirement_name("adafruit-blinka>=8.0.0") == "adafruit-blinka"
    assert compat_ci.requirement_name("Sense_Hat") == "sense-hat"
    assert compat_ci.requirement_name("# only a comment") is None
    assert compat_ci.requirement_name("") is None
