# Virtual Environment Space Optimization Proposal

## Current Space Usage (Estimated)
- Base venv (RQB2): ~400MB
- v1.4 venv (RQB2-v14): ~350MB  
- v0.44 venv (RQB2-v044): ~300MB (disabled)
- **Total**: ~1.05GB for Python environments

## Proposed Optimization Strategies

### Strategy 1: Single Unified Environment ⭐ RECOMMENDED
```bash
# One venv with version-specific imports
/home/rasqberry/RasQberry-Two/venv/
├── RQB2-unified/
│   ├── lib/python3.11/site-packages/
│   │   ├── qiskit/              # Latest 2.x
│   │   ├── qiskit_legacy_14/    # Qiskit 1.4 isolated
│   │   └── shared_deps/         # numpy, matplotlib, etc.
│   └── bin/activate
```

**Implementation:**
- Create helper module for version selection
- Modify demo scripts to specify Qiskit version
- Use importlib for dynamic version loading

**Space Savings**: ~70% (350MB total vs 1.05GB)

### Strategy 2: Symlinked Dependencies
```bash
# Keep separate venvs but share large common packages
RQB2/lib/python3.11/site-packages/numpy/        # Original
RQB2-v14/lib/python3.11/site-packages/numpy/    # Symlink to above
```

**Space Savings**: ~40% (630MB total)

### Strategy 3: Conda-style Environment Layering
- Base environment with common scientific packages
- Overlay environments for version-specific Qiskit

**Space Savings**: ~50-60%

## Demo Script Modifications Required

### get_demo_venv() Helper Update
```bash
get_demo_venv() {
    local DEMO_NAME="$1"
    local QISKIT_VERSION="${2:-latest}"  # New parameter
    
    case "$QISKIT_VERSION" in
        "1.4"|"v14")
            export PYTHONPATH="/home/rasqberry/RasQberry-Two/venv/RQB2-unified/legacy/qiskit-1.4:$PYTHONPATH"
            ;;
        "latest"|*)
            # Use default path
            ;;
    esac
    
    echo "/home/rasqberry/RasQberry-Two/venv/RQB2-unified/bin/activate"
}
```

## Recommended Implementation

**Phase 1**: Implement Strategy 1 (Unified Environment)
- Lowest complexity
- Maximum space savings
- Maintains compatibility

**Phase 2**: If needed, add conda-style layering for more complex scenarios